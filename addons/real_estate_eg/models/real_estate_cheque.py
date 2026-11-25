from odoo import api, fields, models
from odoo.exceptions import UserError

# BR-41: a cheque's states, in order.
CHEQUE_STATE = [
    ("held", "Held"),
    ("deposited", "Deposited"),
    ("cleared", "Cleared"),
    ("bounced", "Bounced"),
]

# BR-41: the only moves. Cleared and bounced are final; a bounced cheque is
# replaced by a new held one on the same line (AC-13.3).
TRANSITIONS = {
    "held": ("deposited",),
    "deposited": ("cleared", "bounced"),
}

# What is written on the cheque: editable only while it is held.
LOCKED_FIELDS = {"name", "bank_name", "date", "amount", "line_id"}


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

    def _check_lines_open(self, lines):
        """AC-13.1: cheques go only on lines of a contract that binds."""
        if any(
            line.contract_id.state not in ("confirmed", "delivered") for line in lines
        ):
            raise UserError(
                self.env._(
                    "Cheques are recorded only on confirmed or delivered contracts."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_lines_open(
            self.env["real.estate.installment"].browse(
                {vals["line_id"] for vals in vals_list if vals.get("line_id")}
            )
        )
        # AC-13.1: a new cheque is always held, whatever the values say.
        for vals in vals_list:
            vals["state"] = "held"
        return super().create(vals_list)

    def write(self, vals):
        # BR-41: checked here, not only by hiding buttons, so the rule holds
        # for every caller: RPC, imports, code, and the superuser too.
        if "state" in vals:
            for cheque in self:
                new = vals["state"]
                if new != cheque.state and new not in TRANSITIONS.get(cheque.state, ()):
                    raise UserError(
                        self.env._(
                            "A cheque cannot go from %(old)s to %(new)s.",
                            old=dict(CHEQUE_STATE)[cheque.state],
                            new=dict(CHEQUE_STATE).get(new, new),
                        )
                    )
        # Once the bank has the cheque, what is written on it is history.
        if LOCKED_FIELDS.intersection(vals) and any(c.state != "held" for c in self):
            raise UserError(self.env._("Only a held cheque can be corrected."))
        if vals.get("line_id"):
            self._check_lines_open(
                self.env["real.estate.installment"].browse(vals["line_id"])
            )
        return super().write(vals)

    # BR-41: the buttons only ask write() for the next state.

    def action_deposit(self):
        return self.write({"state": "deposited"})

    def action_clear(self):
        return self.write({"state": "cleared"})

    def action_bounce(self):
        return self.write({"state": "bounced"})
