from odoo import fields, models

from .res_company import INCOME_TYPES, LIABILITY_TYPES


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
    # §6.4 collection policy (BR-26 - BR-28, BR-30, BR-31).
    re_late_fee_rate = fields.Float(
        related="company_id.re_late_fee_rate", readonly=False
    )
    re_late_fee_cap = fields.Float(related="company_id.re_late_fee_cap", readonly=False)
    re_late_fee_account_id = fields.Many2one(
        related="company_id.re_late_fee_account_id",
        readonly=False,
        check_company=True,
        domain=[("account_type", "in", INCOME_TYPES)],
    )
    re_grace_days = fields.Integer(related="company_id.re_grace_days", readonly=False)
    re_at_risk_days = fields.Integer(
        related="company_id.re_at_risk_days", readonly=False
    )
    # BR-53 (v1.1).
    re_reservation_hold_days = fields.Integer(
        related="company_id.re_reservation_hold_days", readonly=False
    )
