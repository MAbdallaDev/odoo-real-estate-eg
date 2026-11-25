from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Liability account types: the money is owed back to the customer (advances)
# or held for the compound (deposits), so it is never revenue.
LIABILITY_TYPES = ("liability_current", "liability_non_current")


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

    @api.constrains("re_retention_percent", "re_invoice_lead_days")
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
