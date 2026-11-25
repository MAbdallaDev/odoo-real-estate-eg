from odoo import Command, api, fields, models
from odoo.exceptions import UserError

# §5.3: a schedule line is a down payment, an installment or the maintenance
# deposit.
LINE_TYPE = [
    ("down_payment", "Down Payment"),
    ("installment", "Installment"),
    ("maintenance", "Maintenance Deposit"),
]

# §5.3: a line's payment state, read from its invoice (BR-24). "Overdue" is
# computed from dates in Story 05, it is not a state.
LINE_STATE = [
    ("scheduled", "Scheduled"),
    ("invoiced", "Invoiced"),
    ("partially_paid", "Partially Paid"),
    ("paid", "Paid"),
    ("cancelled", "Cancelled"),
]


class RealEstateInstallment(models.Model):
    """US-02: one line of a contract's payment schedule. Lines are made by the
    schedule generator (Step 6), never typed by hand."""

    _name = "real.estate.installment"
    _description = "Payment Schedule Line"
    _order = "contract_id, sequence, id"

    # Same shape as sale.order.line.order_id: lines live and die with the contract.
    contract_id = fields.Many2one(
        "real.estate.contract", required=True, index=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    line_type = fields.Selection(LINE_TYPE, required=True)
    number = fields.Integer(help="k for installment k; 0 for the other lines.")
    name = fields.Char(compute="_compute_name")
    amount = fields.Monetary(required=True)
    # BR-18: empty for a deposit due at delivery until the contract is delivered.
    date_due = fields.Date(string="Due Date")
    company_id = fields.Many2one(
        related="contract_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="contract_id.currency_id")

    # BR-22 / BR-25: one customer invoice per line, linked once. Only accounting
    # users see the link; everyone else reads the line's own state (Step 4).
    invoice_id = fields.Many2one(
        "account.move",
        readonly=True,
        copy=False,
        index="btree_not_null",
        groups="account.group_account_invoice",
    )
    invoice_date = fields.Date(related="invoice_id.invoice_date", store=True)
    # BR-26: nothing is late for the time before the line was invoiced.
    date_effective_due = fields.Date(
        string="Effective Due Date",
        compute="_compute_date_effective_due",
        store=True,
    )

    # BR-16: amounts are whole EGP and never 0 or less (a 0 line is left out).
    _amount_positive = models.Constraint(
        "CHECK (amount > 0)", "A schedule line must have an amount above 0."
    )

    @api.depends("line_type", "number")
    def _compute_name(self):
        labels = dict(LINE_TYPE)
        for line in self:
            label = labels.get(line.line_type, "")
            if line.line_type == "installment":
                label = self.env._("Installment %(number)s", number=line.number)
            line.name = label

    # BR-24: state and amounts come from accounting, stored on the line so that
    # agents and collections read them without rights on invoices.
    state = fields.Selection(
        LINE_STATE,
        string="Status",
        compute="_compute_payment",
        store=True,
        index=True,
    )
    amount_residual = fields.Monetary(
        string="Outstanding", compute="_compute_payment", store=True
    )
    amount_paid = fields.Monetary(string="Paid", compute="_compute_payment", store=True)

    @api.depends(
        "contract_id.state",
        "invoice_id.payment_state",
        "invoice_id.amount_total",
        "invoice_id.amount_residual",
        "invoice_id.reversal_move_ids.state",
        "invoice_id.reversal_move_ids.amount_total",
    )
    def _compute_payment(self):
        for line in self:
            invoice = line.invoice_id
            # A credit note lowers the residual like a payment does, but it is
            # not money received (BR-33), so it is left out of "paid".
            credited = sum(
                invoice.reversal_move_ids.filtered(
                    lambda move: move.state == "posted"
                ).mapped("amount_total")
            )
            line.amount_residual = invoice.amount_residual
            line.amount_paid = (
                invoice.amount_total - invoice.amount_residual - credited
                if invoice
                else 0
            )
            if line.contract_id.state == "cancelled":
                line.state = "cancelled"
            elif not invoice:
                line.state = "scheduled"
            # "In payment" (Accountant app, before bank matching) is paid too.
            elif invoice.payment_state in ("paid", "in_payment"):
                line.state = "paid"
            elif invoice.payment_state == "partial":
                line.state = "partially_paid"
            else:
                line.state = "invoiced"

    @api.depends("date_due", "invoice_date")
    def _compute_date_effective_due(self):
        for line in self:
            dates = [d for d in (line.date_due, line.invoice_date) if d]
            line.date_effective_due = max(dates) if dates else False

    # ------------------------------------------------------------------
    # BR-24 / BR-29: payment history, read from accounting
    # ------------------------------------------------------------------

    def _payment_history(self):
        """(date, amount) of every payment matched with this line's invoice,
        each from its own accounting date (BR-24), so a payment entered late
        with an earlier date counts from that earlier date. Credit notes are
        not payments (BR-33); exchange differences do not apply (EGP only).
        Read as superuser: only accounting users can read invoices."""
        self.ensure_one()
        invoice = self.sudo().invoice_id
        if not invoice:
            return []
        history = []
        # One entry per partial reconciliation on the receivable line; "aml"
        # is the other side (the payment's line), sorted by date.
        for partial in invoice._get_all_reconciled_invoice_partials():
            counterpart = partial["aml"]
            if partial["is_exchange"] or counterpart.move_id.move_type == "out_refund":
                continue
            history.append((counterpart.date, partial["amount"]))
        return history

    # ------------------------------------------------------------------
    # BR-22 / BR-23 / BR-25 / BR-43 / BR-44: invoicing
    # ------------------------------------------------------------------

    def _line_product_and_account(self):
        """The product and the liability account for this line's type."""
        self.ensure_one()
        company = self.company_id
        if self.line_type == "maintenance":
            # BR-23: held money for the compound, not revenue.
            product = self.env.ref("real_estate_eg.product_maintenance_deposit")
            account = company.re_maintenance_account_id
            setting = self.env._("Maintenance Deposits")
        else:
            # BR-43: customer advances, not revenue, before and after delivery.
            xmlid = (
                "real_estate_eg.product_down_payment"
                if self.line_type == "down_payment"
                else "real_estate_eg.product_installment"
            )
            product = self.env.ref(xmlid)
            account = company.re_advance_account_id
            setting = self.env._("Customer Advances")
        if not account:
            raise UserError(
                self.env._(
                    "Set the %(setting)s account in Settings > Real Estate first.",
                    setting=setting,
                )
            )
        return product, account

    def _invoice_vals(self, invoice_date):
        """Values of this line's customer invoice."""
        self.ensure_one()
        product, account = self._line_product_and_account()
        contract = self.contract_id
        return {
            "move_type": "out_invoice",
            "company_id": self.company_id.id,
            "partner_id": contract.partner_id.id,
            "invoice_date": invoice_date,
            # BR-26: the invoice falls due on the later of the two dates.
            "invoice_date_due": max(self.date_due or invoice_date, invoice_date),
            # No payment term: the due date above is the only one.
            "invoice_payment_term_id": False,
            "invoice_origin": contract.name,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": product.id,
                        "name": f"{contract.name} - {self.name}",
                        "quantity": 1,
                        "price_unit": self.amount,
                        "account_id": account.id,
                        # BR-44: no tax, even if the product, the account or
                        # the company has a default sales tax.
                        "tax_ids": [Command.clear()],
                    }
                )
            ],
        }

    def _create_invoices(self, invoice_date):
        """Post one customer invoice per line that has none yet and link it.

        Runs as superuser: the sales manager and the nightly job have no
        accounting rights, and BR-19 locks the line once it is confirmed."""
        lines = self.sudo().filtered(lambda line: not line.invoice_id)  # BR-25
        if not lines:
            return self.env["account.move"]
        # BR-22: no line is invoiced before its contract is confirmed.
        if any(
            line.contract_id.state not in ("confirmed", "delivered") for line in lines
        ):
            raise UserError(
                self.env._("Only lines of a confirmed contract can be invoiced.")
            )
        moves = self.env["account.move"]
        # Each company's invoices go to that company's sales journal.
        for company, company_lines in lines.grouped("company_id").items():
            vals_list = [line._invoice_vals(invoice_date) for line in company_lines]
            Move = self.env["account.move"].sudo().with_company(company)
            company_moves = Move.create(vals_list)
            company_moves.action_post()
            for line, move in zip(company_lines, company_moves, strict=True):
                line.invoice_id = move
            moves |= company_moves
        return moves

    def _credit_unpaid(self, credit_date):
        """BR-34: credit exactly what is still owed on each invoiced line and
        match it with the invoice. One path for both cases: an unpaid invoice
        is credited in full, a partly paid one for its remainder only. (Odoo's
        reversal wizard always credits the full invoice, which would "refund"
        money the customer really paid.) Runs as superuser, like invoicing."""
        refunds = self.env["account.move"]
        for line in self.sudo().filtered(lambda x: x.invoice_id.amount_residual > 0):
            invoice = line.invoice_id
            product, account = line._line_product_and_account()
            refund = (
                self.env["account.move"]
                .sudo()
                .with_company(line.company_id)
                .create(
                    {
                        "move_type": "out_refund",
                        "company_id": line.company_id.id,
                        "partner_id": invoice.partner_id.id,
                        "invoice_date": credit_date,
                        "invoice_payment_term_id": False,
                        "invoice_origin": invoice.invoice_origin,
                        # Links the credit note to its invoice (reversal_move_ids).
                        "reversed_entry_id": invoice.id,
                        "ref": self.env._("Cancellation of %s", invoice.name),
                        "invoice_line_ids": [
                            Command.create(
                                {
                                    "product_id": product.id,
                                    "name": invoice.invoice_line_ids[:1].name,
                                    "quantity": 1,
                                    "price_unit": invoice.amount_residual,
                                    "account_id": account.id,
                                    "tax_ids": [Command.clear()],  # BR-44
                                }
                            )
                        ],
                    }
                )
            )
            refund.action_post()
            # Match the credit note with the invoice on the receivable account.
            receivable = (invoice.line_ids | refund.line_ids).filtered(
                lambda move_line: move_line.account_id.account_type
                == "asset_receivable"
                and not move_line.reconciled
            )
            receivable.reconcile()
            refunds |= refund
        return refunds

    # ------------------------------------------------------------------
    # BR-19: a schedule changes only while its contract is draft.
    # ------------------------------------------------------------------

    def _check_schedule_editable(self, contracts):
        """Refused for everyone once the contract is not draft, managers too.
        Only the superuser passes (Story 04's nightly job links invoices)."""
        if self.env.su:
            return
        if any(contract.state != "draft" for contract in contracts):
            raise UserError(
                self.env._(
                    "The schedule is locked once the contract is confirmed (BR-19)."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        contract_ids = {
            vals["contract_id"] for vals in vals_list if vals.get("contract_id")
        }
        self._check_schedule_editable(
            self.env["real.estate.contract"].browse(contract_ids)
        )
        return super().create(vals_list)

    def write(self, vals):
        contracts = self.contract_id
        if vals.get("contract_id"):
            contracts |= contracts.browse(vals["contract_id"])
        self._check_schedule_editable(contracts)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_locked(self):
        self._check_schedule_editable(self.contract_id)
