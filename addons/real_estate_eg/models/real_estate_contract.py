from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.schedule import compute_schedule
from .real_estate_plan_template import FREQUENCY_MONTHS

# BR-09: the only states. Same shape as SALE_ORDER_STATE in sale/models/sale_order.py.
CONTRACT_STATE = [
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
    ("delivered", "Delivered"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]


class RealEstateContract(models.Model):
    _name = "real.estate.contract"
    _description = "Real Estate Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # chatter and activities
    _check_company_auto = True
    _order = "id desc"
    # Anyone who can read a contract may log a note on it (as sale.order does):
    # collections officers follow up payments without edit rights (BR-35).
    _mail_post_access = "read"

    # BR-07: reference from a sequence, set in create().
    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        index="trigram",
        default=lambda self: self.env._("New"),
    )
    # BR-07: one customer, one unit, one sales agent.
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
        check_company=True,
    )
    unit_id = fields.Many2one(
        "real.estate.unit",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    project_id = fields.Many2one(related="unit_id.project_id", store=True)
    user_id = fields.Many2one(
        "res.users",
        string="Sales Agent",
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env.user,
    )
    # The contract's company is its unit's company.
    company_id = fields.Many2one(related="unit_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    # BR-07: set on the draft; checked and filled on confirmation (Step 9).
    date = fields.Date(string="Contract Date", tracking=True, copy=False)
    confirmation_date = fields.Date(readonly=True, copy=False)
    # BR-11: the handover date; editable on a confirmed contract (form view),
    # filled with today by action_deliver() when left empty.
    delivery_date = fields.Date(copy=False, tracking=True)
    cancel_reason = fields.Text(readonly=True, copy=False, tracking=True)
    # BR-08: frozen at the unit's list price; depends on unit_id only.
    price = fields.Monetary(
        compute="_compute_price", store=True, precompute=True, tracking=True
    )
    # BR-07: the payment plan. Set by the generate wizard (Step 6), not typed.
    plan_id = fields.Many2one(
        "real.estate.plan.template",
        string="Payment Plan",
        readonly=True,
        tracking=True,
        check_company=True,
    )
    # US-02: the schedule. Same shape as sale.order.order_line.
    installment_ids = fields.One2many(
        "real.estate.installment", "contract_id", string="Schedule", copy=False
    )
    # BR-10 / BR-18: down payment + installments; the deposit is not in the price.
    schedule_total = fields.Monetary(compute="_compute_schedule_total")
    state = fields.Selection(
        CONTRACT_STATE,
        string="Status",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        default="draft",
    )

    # BR-04 in the database: at most one contract per unit that is not
    # cancelled. Holds even when two users save at the same moment.
    _unit_live_unique = models.UniqueIndex(
        "(unit_id) WHERE state != 'cancelled'",
        "This unit already has a contract that is not cancelled.",
    )

    @api.constrains("delivery_date", "date")
    def _check_delivery_date(self):
        # BR-11: checked on every save, not only by action_deliver(), so a
        # wrong date typed on the form is never stored.
        today = fields.Date.context_today(self)
        for contract in self.filtered("delivery_date"):
            if contract.delivery_date > today:
                raise ValidationError(
                    self.env._("The delivery date cannot be in the future.")
                )
            if contract.date and contract.delivery_date < contract.date:
                raise ValidationError(
                    self.env._("The delivery date cannot be before the contract date.")
                )

    @api.depends("unit_id")
    def _compute_price(self):
        # Not "unit_id.list_price": a later list price change must not reach
        # existing contracts (AC-01.2). A new unit re-takes its price (AC-01.6).
        for contract in self:
            contract.price = contract.unit_id.list_price

    @api.depends("installment_ids.amount", "installment_ids.line_type")
    def _compute_schedule_total(self):
        for contract in self:
            contract.schedule_total = sum(
                line.amount
                for line in contract.installment_ids
                if line.line_type != "maintenance"
            )

    def _check_unit_free(self, unit_ids):
        """BR-04 / AC-01.3: a clear message before the database refuses.

        It names only the existing contract's reference (no customer, agent or
        price). sudo(): from Story 06 an agent cannot see another agent's
        contract, but the unit is still taken.
        """
        if len(unit_ids) != len(set(unit_ids)):
            raise ValidationError(self.env._("Two contracts cannot share one unit."))
        live = self.sudo().search(
            [
                ("unit_id", "in", unit_ids),
                ("state", "!=", "cancelled"),
                ("id", "not in", self.ids),
            ],
            limit=1,
        )
        if live:
            raise ValidationError(
                self.env._(
                    "Unit %(unit)s already has contract %(reference)s.",
                    unit=live.unit_id.code,
                    reference=live.name,
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        # BR-04: refuse a taken unit before drawing a reference (AC-01.3).
        self._check_unit_free(
            [vals["unit_id"] for vals in vals_list if vals.get("unit_id")]
        )
        # Same pattern as sale.order.create(): draw the reference from the
        # sequence, dated by the contract date so the year matches it.
        for vals in vals_list:
            if vals.get("name", self.env._("New")) == self.env._("New"):
                unit = self.env["real.estate.unit"].browse(vals.get("unit_id"))
                vals["name"] = self.env["ir.sequence"].with_company(
                    unit.company_id
                ).next_by_code(
                    "real.estate.contract",
                    sequence_date=vals.get("date") or fields.Date.context_today(self),
                ) or self.env._("New")
        return super().create(vals_list)

    def write(self, vals):
        not_draft = self.filtered(lambda c: c.state != "draft")
        # BR-35: an agent edits a contract only while it is draft. A manager
        # edits all; system jobs run as superuser (env.su).
        if (
            not_draft
            and not self.env.su
            and not self.env.user.has_group("real_estate_eg.group_real_estate_manager")
        ):
            raise AccessError(
                self.env._(
                    "Only a sales manager can change a contract that is not draft."
                )
            )
        # BR-08 / BR-19: the unit, and so the price, is fixed once confirmed.
        if "unit_id" in vals and not_draft:
            raise UserError(
                self.env._("The unit can be changed only on a draft contract.")
            )
        if vals.get("unit_id"):
            # Writing one unit on several contracts would share it too.
            self._check_unit_free([vals["unit_id"]] * len(self))
        self._drop_stale_schedule(vals)
        return super().write(vals)

    def _drop_stale_schedule(self, vals):
        """A new unit (so a new price) or a new contract date makes a draft's
        schedule wrong (BR-16, BR-17): its lines are deleted and the schedule
        must be generated again. Only a real change counts: confirmation
        writes the same date again and must keep the lines."""
        if "installment_ids" in vals:
            return
        new_date = fields.Date.to_date(vals["date"]) if "date" in vals else None
        stale = self.filtered(
            lambda c: c.state == "draft"
            and c.installment_ids
            and (
                ("unit_id" in vals and vals["unit_id"] != c.unit_id.id)
                # A generated schedule always has a date; confirmation filling
                # an empty date (BR-07) is not a change of schedule.
                or ("date" in vals and c.date and new_date != c.date)
            )
        )
        stale.installment_ids.unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft(self):
        # BR-13: same shape as sale.order's _unlink_except_draft_or_cancel.
        if any(contract.state != "draft" for contract in self):
            raise UserError(
                self.env._(
                    "Only draft contracts can be deleted. Cancel the contract instead."
                )
            )

    # ------------------------------------------------------------------
    # State actions (BR-09). Shape borrowed from sale.order.action_confirm().
    # ------------------------------------------------------------------

    def _check_manager(self):
        """BR-10 / BR-11 / BR-32: some actions belong to the sales manager only."""
        if not self.env.user.has_group("real_estate_eg.group_real_estate_manager"):
            raise AccessError(self.env._("Only a sales manager can do this."))

    def action_confirm(self):
        """US-10 / BR-10: a manager approves the contract before it binds."""
        self._check_manager()
        for contract in self:
            error = contract._confirmation_error_message()
            if error:
                raise UserError(error)
        today = fields.Date.context_today(self)
        for contract in self:
            contract.write(
                {
                    "state": "confirmed",
                    "confirmation_date": today,
                    # BR-07: an empty contract date becomes the confirmation date.
                    "date": contract.date or today,
                }
            )
        return True

    def action_deliver(self):
        """US-11 / BR-11: a manager records the handover of a confirmed contract.
        Installments continue as scheduled; the maintenance deposit falling due
        is Story 04."""
        self._check_manager()
        today = fields.Date.context_today(self)
        for contract in self:
            if contract.state != "confirmed":
                raise UserError(
                    self.env._("Only a confirmed contract can be marked delivered.")
                )
        # The date itself is checked by _check_delivery_date on save.
        for contract in self:
            contract.write(
                {"state": "delivered", "delivery_date": contract.delivery_date or today}
            )
        return True

    def action_cancel(self):
        """US-09 / BR-32: a draft is cancelled at once by its agent or a
        manager; a confirmed contract needs a manager and a written reason
        (the cancel dialog); a delivered or closed one cannot be cancelled."""
        if any(c.state in ("delivered", "closed") for c in self):
            raise UserError(
                self.env._("A delivered or closed contract cannot be cancelled.")
            )
        if any(c.state == "cancelled" for c in self):
            raise UserError(self.env._("This contract is already cancelled."))
        if any(c.state == "confirmed" for c in self):
            self._check_manager()
            self.ensure_one()
            return {
                "type": "ir.actions.act_window",
                "name": self.env._("Cancel Contract"),
                "res_model": "real.estate.contract.cancel",
                "view_mode": "form",
                "target": "new",
                "context": {"default_contract_id": self.id},
            }
        # Drafts: their own agent, or a manager (record rules come in Story 06).
        is_manager = self.env.user.has_group("real_estate_eg.group_real_estate_manager")
        if not is_manager and any(c.user_id != self.env.user for c in self):
            raise AccessError(
                self.env._("Only the contract's agent or a manager can cancel it.")
            )
        self.write({"state": "cancelled"})
        return True

    # ------------------------------------------------------------------
    # US-02: generate the schedule from a plan (BR-14 to BR-20).
    # ------------------------------------------------------------------

    def action_generate_schedule(self):
        """Open the dialog to pick a plan; the button shows on drafts only."""
        self.ensure_one()
        self._check_schedule_draft()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Generate Schedule"),
            "res_model": "real.estate.schedule.generate",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_contract_id": self.id,
                "default_plan_id": self.plan_id.id,
            },
        }

    def _check_schedule_draft(self):
        # BR-19: a schedule is (re)generated only while the contract is draft.
        if self.state != "draft":
            raise UserError(
                self.env._("The schedule can be generated only on a draft contract.")
            )

    def _generate_schedule(self, plan):
        """US-02: replace the schedule with lines from `plan`. The amounts and
        dates come from compute_schedule(), the maintainer's pure function."""
        self.ensure_one()
        self._check_schedule_draft()
        # BR-17: every due date is counted from the contract date.
        if not self.date:
            raise UserError(
                self.env._("Set the contract date before generating the schedule.")
            )
        lines = compute_schedule(
            price=self.price,
            contract_date=self.date,
            down_payment_percent=plan.down_payment_percent,
            installment_count=plan.installment_count,
            step_months=FREQUENCY_MONTHS.get(plan.frequency, 0),
            first_installment_months=plan.first_installment_months,
            maintenance_percent=plan.maintenance_percent,
            maintenance_at_signing=plan.maintenance_due == "signing",
        )
        # Only a tiny price with many installments can leave the last one at
        # 0 or less (rounded-up lines eat the remainder).
        if any(line["amount"] <= 0 for line in lines):
            raise UserError(
                self.env._(
                    "The price %(price)s is too small for plan %(plan)s.",
                    price=self.price,
                    plan=plan.code,
                )
            )
        self.installment_ids.unlink()
        self.write(
            {
                "plan_id": plan.id,
                "installment_ids": [
                    Command.create(dict(line, sequence=index))
                    for index, line in enumerate(lines, start=1)
                ],
            }
        )

    def _cancel_with_reason(self, reason):
        """BR-32: called by the cancel dialog for a confirmed contract.
        Retention and refunds from real payments are Story 04."""
        self.ensure_one()
        self._check_manager()
        if self.state != "confirmed":
            raise UserError(
                self.env._("Only a confirmed contract is cancelled this way.")
            )
        if not (reason or "").strip():
            raise UserError(self.env._("A written reason is required."))
        self.write({"state": "cancelled", "cancel_reason": reason.strip()})

    def _confirmation_error_message(self):
        """Why this contract cannot be confirmed, or False. Same role as
        sale.order._confirmation_error_message(); Story 03 adds the schedule
        check (BR-10) here."""
        self.ensure_one()
        if self.state != "draft":
            return self.env._("Only a draft contract can be confirmed.")
        # BR-07: the contract date cannot be later than the confirmation day.
        if self.date and self.date > fields.Date.context_today(self):
            return self.env._(
                "The contract date cannot be later than the confirmation date."
            )
        # BR-05: identity of an individual buyer; a company has no check in v1.
        partner = self.partner_id
        if not partner.is_company:
            if not partner.nationality:
                return self.env._("Set the customer's nationality first.")
            if partner.nationality == "egyptian" and not partner.national_id:
                return self.env._("An Egyptian customer needs a national ID.")
            if partner.nationality == "foreign" and not partner.passport_number:
                return self.env._("A foreign customer needs a passport number.")
        return False
