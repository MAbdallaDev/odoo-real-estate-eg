from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

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
    cancel_reason = fields.Text(readonly=True, copy=False)
    # BR-08: frozen at the unit's list price; depends on unit_id only.
    price = fields.Monetary(
        compute="_compute_price", store=True, precompute=True, tracking=True
    )
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

    @api.depends("unit_id")
    def _compute_price(self):
        # Not "unit_id.list_price": a later list price change must not reach
        # existing contracts (AC-01.2). A new unit re-takes its price (AC-01.6).
        for contract in self:
            contract.price = contract.unit_id.list_price

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
        return super().write(vals)

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
            if contract.delivery_date and contract.delivery_date > today:
                raise UserError(
                    self.env._("The delivery date cannot be in the future.")
                )
            if contract.delivery_date and contract.delivery_date < contract.date:
                raise UserError(
                    self.env._("The delivery date cannot be before the contract date.")
                )
        for contract in self:
            contract.write(
                {"state": "delivered", "delivery_date": contract.delivery_date or today}
            )
        return True

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
