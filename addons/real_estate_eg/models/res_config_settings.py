from odoo import fields, models

from .res_company import LIABILITY_TYPES


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Same fields as on the company (BR-22, BR-23, BR-33, BR-43), edited in Settings.
    re_advance_account_id = fields.Many2one(
        related="company_id.re_advance_account_id",
        readonly=False,
        check_company=True,
        domain=[("account_type", "in", LIABILITY_TYPES)],
    )
    re_maintenance_account_id = fields.Many2one(
        related="company_id.re_maintenance_account_id",
        readonly=False,
        check_company=True,
        domain=[("account_type", "in", LIABILITY_TYPES)],
    )
    re_retention_percent = fields.Float(
        related="company_id.re_retention_percent", readonly=False
    )
    re_invoice_lead_days = fields.Integer(
        related="company_id.re_invoice_lead_days", readonly=False
    )
