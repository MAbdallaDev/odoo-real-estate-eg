from datetime import timedelta
from decimal import Decimal

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools.schedule import compute_schedule, half_up
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
    # BR-33 / AC-09.3: computed from real payments when a confirmed contract is
    # cancelled, before any credit note. Issuing the refund is the accountant's
    # manual step.
    retention_amount = fields.Monetary(readonly=True, copy=False, tracking=True)
    refundable_amount = fields.Monetary(readonly=True, copy=False, tracking=True)
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
    # AC-03.5 / BR-24: totals read from accounting through the lines.
    # Outstanding = invoiced but not paid; lines not invoiced yet are not owed.
    amount_paid = fields.Monetary(string="Total Paid", compute="_compute_amounts")
    amount_outstanding = fields.Monetary(
        string="Total Outstanding", compute="_compute_amounts"
    )
    # BR-30: late fees, summed from the lines' unrounded amounts and rounded
    # once (Monetary rounds to piastres when it is set).
    late_fee_accrued = fields.Monetary(
        string="Accrued Late Fees", compute="_compute_late_fees"
    )
    late_fee_unbilled = fields.Monetary(
        string="Unbilled Late Fees", compute="_compute_late_fees"
    )
    # BR-30: the late-fee invoices billed on this contract. Not schedule lines,
    # so they never accrue a fee (AC-05.9). Accounting users only.
    late_fee_invoice_ids = fields.Many2many(
        "account.move",
        "real_estate_contract_late_fee_invoice_rel",
        "contract_id",
        "move_id",
        string="Late Fee Invoices",
        readonly=True,
        copy=False,
        groups="account.group_account_invoice",
    )
    # BR-31: flagged, never cancelled automatically. A stored compute on the
    # lines, so paying the late line clears it at once.
    at_risk = fields.Boolean(
        compute="_compute_at_risk",
        store=True,
        index=True,
        tracking=True,
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

    @api.depends("installment_ids.amount_paid", "installment_ids.amount_residual")
    def _compute_amounts(self):
        for contract in self:
            lines = contract.installment_ids
            contract.amount_paid = sum(lines.mapped("amount_paid"))
            contract.amount_outstanding = sum(lines.mapped("amount_residual"))

    @api.depends(
        "state",
        "installment_ids.state",
        "installment_ids.days_past_due",
        "company_id.re_at_risk_days",
    )
    def _compute_at_risk(self):
        """BR-31: a live contract with a line not paid and more than the
        company's at-risk days (60) past due. Cleared when no such line
        remains, or when the contract is no longer live."""
        for contract in self:
            limit = contract.company_id.re_at_risk_days
            contract.at_risk = contract.state in ("confirmed", "delivered") and any(
                line.state in ("invoiced", "partially_paid")
                and line.days_past_due > limit
                for line in contract.installment_ids
            )

    @api.depends(
        "installment_ids.late_fee_accrued", "installment_ids.late_fee_unbilled"
    )
    def _compute_late_fees(self):
        for contract in self:
            lines = contract.installment_ids
            contract.late_fee_accrued = sum(lines.mapped("late_fee_accrued"))
            contract.late_fee_unbilled = sum(lines.mapped("late_fee_unbilled"))

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
        # BR-07 / BR-19: the contract date is set on the draft. Once confirmed,
        # the schedule's dates are counted from it, so it is locked too, for
        # everyone but the superuser (the form view alone would not stop an
        # import or an API call).
        if "date" in vals and not_draft and not self.env.su:
            new_date = fields.Date.to_date(vals["date"])
            if any(contract.date != new_date for contract in not_draft):
                raise UserError(
                    self.env._(
                        "The contract date can be changed only on a draft contract."
                    )
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
        # BR-21: every line already due is invoiced at once (the down payment,
        # a deposit due at signing, installments of a backdated contract).
        self._invoice_due_lines(today)
        return True

    def action_deliver(self):
        """US-11 / BR-11: a manager records the handover of a confirmed contract.
        Installments continue as scheduled (AC-11.3); the maintenance deposit
        due at delivery falls due on the delivery date and is invoiced."""
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
        # BR-18 / AC-11.2: the deposit due at delivery gets the delivery date.
        # As superuser: the schedule of a confirmed contract is locked (BR-19).
        for line in self.installment_ids.sudo():
            if line.line_type == "maintenance" and not line.date_due:
                line.date_due = line.contract_id.delivery_date
        # BR-23: invoiced at once, to the maintenance deposits account.
        self._invoice_due_lines(today)
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

    def action_bill_late_fees(self):
        """US-05 / BR-30 / BR-35: a collections officer or a sales manager
        bills a contract's unbilled late fees in one invoice. The system never
        bills them on its own."""
        # The manager group implies the collections group.
        if not self.env.user.has_group("real_estate_eg.group_real_estate_collections"):
            raise AccessError(
                self.env._(
                    "Only a collections officer or a sales manager can bill late fees."
                )
            )
        if any(c.state not in ("confirmed", "delivered") for c in self):
            raise UserError(
                self.env._(
                    "Late fees are billed only on confirmed or delivered contracts."
                )
            )
        today = fields.Date.context_today(self)
        for contract in self:
            contract._bill_late_fees(today)
        return True

    def _bill_late_fees(self, invoice_date):
        """BR-30: one invoice for the sum of the lines' unbilled fees, rounded
        once, half up to whole EGP (BR-45). Each line's billed fee becomes its
        accrued fee, unrounded, so billing again finds nothing (AC-05.7).
        Created as superuser: collections officers have no invoicing rights.
        Returns the invoice, or an empty recordset when nothing is due."""
        self.ensure_one()
        lines = self.installment_ids.sudo().filtered(
            lambda line: line.late_fee_unbilled > 0
        )
        unbilled = [Decimal(str(x)) for x in lines.mapped("late_fee_unbilled")]
        total = half_up(sum(unbilled, Decimal(0)))
        Move = self.env["account.move"].sudo().with_company(self.company_id)
        if total <= 0:
            return Move
        account = self.company_id.re_late_fee_account_id
        if not account:
            raise UserError(
                self.env._("Set the Late Fees account in Settings > Real Estate first.")
            )
        product = self.env.ref("real_estate_eg.product_late_fee")
        invoice = Move.create(
            {
                "move_type": "out_invoice",
                "company_id": self.company_id.id,
                "partner_id": self.partner_id.id,
                "invoice_date": invoice_date,
                "invoice_payment_term_id": False,
                "invoice_origin": self.name,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": self.env._("%s - Late fees", self.name),
                            "quantity": 1,
                            "price_unit": total,
                            "account_id": account.id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        for line in lines:
            line.late_fee_billed = line.late_fee_accrued
        self.sudo().late_fee_invoice_ids = [Command.link(invoice.id)]
        # Collections officers cannot open invoices: the chatter tells them.
        self.message_post(
            body=self.env._(
                "Late fees billed: %(amount)s EGP (%(invoice)s).",
                amount=f"{total:,}",
                invoice=invoice.name,
            )
        )
        return invoice

    def action_generate_schedule(self):
        """Open the dialog to pick a plan; the button shows on drafts only."""
        self.ensure_one()
        # BR-35 / AC-06.3: read-only roles are refused here, not in the dialog.
        self.check_access("write")
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
        """BR-32 / BR-33: called by the cancel dialog for a confirmed contract."""
        self.ensure_one()
        self._check_manager()
        if self.state != "confirmed":
            raise UserError(
                self.env._("Only a confirmed contract is cancelled this way.")
            )
        if not (reason or "").strip():
            raise UserError(self.env._("A written reason is required."))
        # BR-33: the money first, while it still reads real payments only.
        self.write(self._cancellation_amounts())
        # BR-34: then credit what was invoiced but not paid.
        today = fields.Date.context_today(self)
        self.installment_ids._credit_unpaid(today)
        # BR-34: unpaid late-fee invoices too; paid ones are not refunded.
        self._credit_unpaid_late_fees(today)
        # Every line now shows cancelled, set by the module (line state
        # follows the contract); the unit is available again (BR-03).
        self.write({"state": "cancelled", "cancel_reason": reason.strip()})

    def _credit_unpaid_late_fees(self, credit_date):
        """BR-34: credit what is still owed on each late-fee invoice, to the
        account it was billed to. Fees never billed are simply dropped: the
        contract is cancelled and no longer computed (BR-29)."""
        self.ensure_one()
        product = self.env.ref("real_estate_eg.product_late_fee")
        invoices = self.sudo().late_fee_invoice_ids.filtered(
            lambda move: move.state == "posted" and move.amount_residual > 0
        )
        Line = self.env["real.estate.installment"]
        for invoice in invoices:
            account = invoice.invoice_line_ids[:1].account_id
            Line._credit_residual(invoice, product, account, credit_date)

    def _cancellation_amounts(self):
        """BR-33: retention = retention % of what was paid against the down
        payment and installments, half up to whole EGP; refundable = that paid
        amount - retention + any paid maintenance deposit, in full. Paid late
        fees are not refunded: late-fee invoices are not schedule lines. Line
        amount_paid counts payments only, never credit notes."""
        self.ensure_one()
        lines = self.installment_ids
        price_lines = lines.filtered(lambda line: line.line_type != "maintenance")
        paid = Decimal(str(sum(price_lines.mapped("amount_paid"))))
        deposit_paid = sum((lines - price_lines).mapped("amount_paid"))
        percent = Decimal(str(self.company_id.re_retention_percent))
        retention = half_up(paid * percent / Decimal(100))
        return {
            "retention_amount": retention,
            "refundable_amount": float(paid) - retention + deposit_paid,
        }

    def _confirmation_error_message(self):
        """Why this contract cannot be confirmed, or False. Same role as
        sale.order._confirmation_error_message(). The schedule check comes
        last, so a wrong date or identity is reported first."""
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
        # BR-10: a schedule whose down payment + installments equal the price
        # exactly (the maintenance deposit is not part of it, BR-18).
        if not self.installment_ids:
            return self.env._("Generate the schedule first.")
        if self.currency_id.compare_amounts(self.schedule_total, self.price) != 0:
            return self.env._(
                "The schedule adds up to %(total)s, not the contract price %(price)s.",
                total=self.schedule_total,
                price=self.price,
            )
        # BR-43 / BR-23: checked here so nothing binds before it can be invoiced.
        company = self.company_id
        if not company.re_advance_account_id or not company.re_maintenance_account_id:
            return self.env._(
                "Set the Customer Advances and Maintenance Deposits accounts "
                "in Settings > Real Estate first."
            )
        return False

    @api.model
    def _cron_nightly(self, today=None):
        """§5.5, the nightly job, run as superuser across all companies.
        Step 1: invoice every line that has fallen due (BR-22, BR-25).
        Step 2: recompute days past due and late fees (BR-26 - BR-29).
        Step 3: the at-risk flag follows from step 2 (stored compute, BR-31).
        Step 4: close delivered contracts that are fully paid (BR-12).
        `today` is a parameter so tests can run any day."""
        today = today or fields.Date.context_today(self)
        contracts = self.search([("state", "in", ("confirmed", "delivered"))])
        contracts._invoice_due_lines(today)
        self._cron_late_fees(today)
        self._cron_close_paid_contracts()

    @api.model
    def _cron_late_fees(self, today):
        """§5.5 step 2: every invoiced line of a live contract that is not
        paid, or was paid since its fee was last computed (not final yet).
        A fully paid line computed once is final and skipped. Recomputing is
        safe: the fee is overwritten from the payment history (BR-29)."""
        lines = (
            self.env["real.estate.installment"]
            .sudo()
            .search(
                [
                    ("contract_id.state", "in", ("confirmed", "delivered")),
                    ("invoice_id", "!=", False),
                    "|",
                    ("state", "!=", "paid"),
                    ("late_fee_final", "=", False),
                ]
            )
        )
        lines._recompute_late_fees(today)
        return lines

    @api.model
    def _cron_close_paid_contracts(self):
        """BR-12 / AC-12.1: a delivered contract closes once every line is
        paid. A line not invoiced yet is not paid, so a contract with future
        installments stays open. AC-12.2: a confirmed contract never closes.
        BR-12 also waits for late fees: every late-fee invoice paid and no
        accrued fee left unbilled (v1 has no waiver)."""
        delivered = self.search([("state", "=", "delivered")])
        paid = delivered.filtered(
            lambda contract: contract.installment_ids
            and all(line.state == "paid" for line in contract.installment_ids)
            and contract._late_fees_settled()
        )
        paid.write({"state": "closed"})
        return paid

    def _late_fees_settled(self):
        """BR-12: every billed late fee paid ("In payment" counts as paid,
        BR-24) and nothing left to bill. A rest under 0.50 EGP rounds to 0 and
        can never be billed (BR-30), so it does not block closing."""
        self.ensure_one()
        invoices = self.sudo().late_fee_invoice_ids
        unbilled = [
            Decimal(str(x)) for x in self.installment_ids.mapped("late_fee_unbilled")
        ]
        return (
            all(invoice.payment_state in ("paid", "in_payment") for invoice in invoices)
            and half_up(sum(unbilled, Decimal(0))) == 0
        )

    def _invoice_due_lines(self, today):
        """BR-21 / BR-22: invoice every line of these contracts that is due by
        today + the company's lead days and has no invoice yet (BR-25).
        Draft and cancelled contracts are never invoiced."""
        lines = (
            self.env["real.estate.installment"]
            .sudo()
            .search(
                [
                    ("contract_id", "in", self.ids),
                    ("contract_id.state", "in", ("confirmed", "delivered")),
                    ("date_due", "!=", False),
                    ("invoice_id", "=", False),
                ],
                order="date_due, id",
            )
        )
        due = lines.filtered(
            lambda line: line.date_due
            <= today + timedelta(days=line.company_id.re_invoice_lead_days)
        )
        return due._create_invoices(today)
