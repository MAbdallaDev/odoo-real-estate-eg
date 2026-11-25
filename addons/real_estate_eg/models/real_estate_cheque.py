from odoo import api, fields, models
from odoo.exceptions import UserError

# BR-41: a cheque's states, in order.
CHEQUE_STATE = [
    ("held", "Held"),
    ("deposited", "Deposited"),
    ("cleared", "Cleared"),
    ("bounced", "Bounced"),
]


class RealEstateCheque(models.Model):
    """US-13 / BR-40: a post-dated cheque the buyer handed over, linked to one
    schedule line. Its status is information only (BR-42): nothing on the line
    or the contract depends on it, and it creates no accounting entry."""

    _name = "real.estate.cheque"
    _description = "Post-dated Cheque"
    _inherit = ["mail.thread"]  # state changes are logged in the chatter
    _order = "date, id"

    name = fields.Char(string="Cheque Number", required=True, tracking=True)
    # Plain text: collections officers may read res.bank but not add a bank.
    bank_name = fields.Char(string="Bank", required=True, tracking=True)
    date = fields.Date(string="Cheque Date", required=True, tracking=True)
    amount = fields.Monetary(required=True, tracking=True)
    # BR-40: one line, several cheques over time (a bounced one is replaced).
    # Restrict: a line with cheques is never deleted (its schedule is locked
    # anyway once the contract is confirmed, BR-19).
    line_id = fields.Many2one(
        "real.estate.installment",
        string="Schedule Line",
        required=True,
        index=True,
        ondelete="restrict",
    )
    # Stored: the agent record rule and the contract's button read it.
    contract_id = fields.Many2one(related="line_id.contract_id", store=True, index=True)
    partner_id = fields.Many2one(related="line_id.contract_id.partner_id")
    company_id = fields.Many2one(related="line_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="line_id.currency_id")
    state = fields.Selection(
        CHEQUE_STATE,
        string="Status",
        required=True,
        readonly=True,
        copy=False,
        default="held",
        tracking=True,
    )

    _amount_positive = models.Constraint(
        "CHECK (amount > 0)", "A cheque must have an amount above 0."
    )

    @api.model_create_multi
    def create(self, vals_list):
        lines = self.env["real.estate.installment"].browse(
            {vals["line_id"] for vals in vals_list if vals.get("line_id")}
        )
        # AC-13.1: only on a contract that binds.
        if any(
            line.contract_id.state not in ("confirmed", "delivered") for line in lines
        ):
            raise UserError(
                self.env._(
                    "Cheques are recorded only on confirmed or delivered contracts."
                )
            )
        # AC-13.1: a new cheque is always held, whatever the values say.
        for vals in vals_list:
            vals["state"] = "held"
        return super().create(vals_list)
