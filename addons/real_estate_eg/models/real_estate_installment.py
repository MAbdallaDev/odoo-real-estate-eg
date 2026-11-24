from odoo import api, fields, models
from odoo.exceptions import UserError

# §5.3: a schedule line is a down payment, an installment or the maintenance
# deposit. Payment states (scheduled, invoiced, paid...) come in Story 04.
LINE_TYPE = [
    ("down_payment", "Down Payment"),
    ("installment", "Installment"),
    ("maintenance", "Maintenance Deposit"),
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
