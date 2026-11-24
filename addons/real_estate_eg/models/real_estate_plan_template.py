from odoo import api, fields, models
from odoo.exceptions import ValidationError

# BR-14: the four frequencies, and how many months apart the installments fall.
FREQUENCY = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-annual"),
    ("annual", "Annual"),
]
FREQUENCY_MONTHS = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}


class RealEstatePlanTemplate(models.Model):
    """BR-14: a payment plan template. The schedule generator (Steps 4-6)
    reads it; a contract only keeps a link to the plan it was generated from."""

    _name = "real.estate.plan.template"
    _description = "Payment Plan Template"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Short code, e.g. NH-STD-8Q.")
    down_payment_percent = fields.Float(string="Down Payment (%)", required=True)
    installment_count = fields.Integer(string="Installments", required=True)
    frequency = fields.Selection(FREQUENCY, help="Empty for a cash plan.")
    first_installment_months = fields.Integer(
        string="First Installment After (months)",
        help="Months from the contract date to installment 1.",
    )
    maintenance_percent = fields.Float(string="Maintenance Deposit (%)")
    maintenance_due = fields.Selection(
        [("signing", "At signing"), ("delivery", "At delivery")],
        string="Maintenance Deposit Due",
        required=True,
        default="delivery",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )

    # BR-14: a code is unique inside a company, as for projects and units.
    _code_company_unique = models.Constraint(
        "UNIQUE (company_id, code)",
        "A plan code must be unique within its company.",
    )
    _down_payment_percent_range = models.Constraint(
        "CHECK (down_payment_percent >= 0 AND down_payment_percent <= 100)",
        "The down payment must be between 0% and 100%.",
    )
    _maintenance_percent_range = models.Constraint(
        "CHECK (maintenance_percent >= 0 AND maintenance_percent <= 100)",
        "The maintenance deposit must be between 0% and 100%.",
    )
    _counts_not_negative = models.Constraint(
        "CHECK (installment_count >= 0 AND first_installment_months >= 0)",
        "The number of installments and the months cannot be negative.",
    )

    @api.constrains("installment_count", "down_payment_percent", "frequency")
    def _check_installments(self):
        for plan in self:
            # BR-20: a cash plan (0 installments) is valid only with 100% down,
            # or the schedule could not add up to the price.
            if plan.installment_count == 0 and plan.down_payment_percent != 100:
                raise ValidationError(
                    self.env._("A plan with no installments needs a 100% down payment.")
                )
            if plan.installment_count > 0:
                # 100% down would leave installments of 0 EGP.
                if plan.down_payment_percent == 100:
                    raise ValidationError(
                        self.env._(
                            "A 100% down payment leaves nothing for the installments."
                        )
                    )
                if not plan.frequency:
                    raise ValidationError(
                        self.env._("Set how often the installments fall due.")
                    )
