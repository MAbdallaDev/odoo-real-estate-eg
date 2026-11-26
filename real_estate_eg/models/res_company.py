from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Liability account types: the money is owed back to the customer (advances)
# or held for the compound (deposits), so it is never revenue.
LIABILITY_TYPES = ("liability_current", "liability_non_current")
# BR-30: late fees are income the developer earns, not customer money it holds.
INCOME_TYPES = ("income", "income_other")


class ResCompany(models.Model):
    _inherit = "res.company"

    # BR-43: down payment and installment invoices post here, not to revenue.
    re_advance_account_id = fields.Many2one(
        "account.account",
        string="Customer Advances Account",
        check_company=True,
        domain=[("account_type", "in", LIABILITY_TYPES)],
    )
    # BR-23: the maintenance deposit is held money, a liability.
    re_maintenance_account_id = fields.Many2one(
        "account.account",
        string="Maintenance Deposits Account",
        check_company=True,
        domain=[("account_type", "in", LIABILITY_TYPES)],
    )
    # BR-33: share of paid down payment and installments kept on cancellation.
    re_retention_percent = fields.Float(string="Cancellation Retention (%)", default=15)
    # BR-22: invoice a line this many days before its due date.
    re_invoice_lead_days = fields.Integer(string="Invoice Lead Days", default=0)

    # §6.4 collection policy. Company settings, because a real developer sets
    # them with its lawyer (12% a year is above the Civil Code Art. 227 cap).
    # BR-27: simple interest, % per month, 1/30 of it per day.
    re_late_fee_rate = fields.Float(string="Late Fee Rate (% per month)", default=1)
    # BR-28: a line's total fee never exceeds this % of its amount.
    re_late_fee_cap = fields.Float(string="Late Fee Cap (% of the line)", default=10)
    # BR-30: billed late fees post here.
    re_late_fee_account_id = fields.Many2one(
        "account.account",
        string="Late Fees Account",
        check_company=True,
        domain=[("account_type", "in", INCOME_TYPES)],
    )
    # BR-26: a line is overdue once this many days after its effective due date.
    re_grace_days = fields.Integer(string="Grace Period (days)", default=7)
    # BR-31: more than this many days past due flags the contract at risk.
    re_at_risk_days = fields.Integer(string="At Risk After (days)", default=60)

    @api.constrains(
        "re_retention_percent",
        "re_invoice_lead_days",
        "re_late_fee_rate",
        "re_late_fee_cap",
        "re_grace_days",
        "re_at_risk_days",
    )
    def _check_real_estate_settings(self):
        for company in self:
            if not 0 <= company.re_retention_percent <= 100:
                raise ValidationError(
                    self.env._("The retention must be between 0 and 100%.")
                )
            if company.re_invoice_lead_days < 0:
                raise ValidationError(
                    self.env._("Invoice lead days cannot be negative.")
                )
            if not 0 <= company.re_late_fee_rate <= 100:
                raise ValidationError(
                    self.env._("The late fee rate must be between 0 and 100%.")
                )
            if not 0 <= company.re_late_fee_cap <= 100:
                raise ValidationError(
                    self.env._("The late fee cap must be between 0 and 100%.")
                )
            if company.re_grace_days < 0 or company.re_at_risk_days < 0:
                raise ValidationError(
                    self.env._("Grace and at-risk days cannot be negative.")
                )
