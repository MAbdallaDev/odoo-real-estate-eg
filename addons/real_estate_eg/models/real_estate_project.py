from odoo import fields, models


class RealEstateProject(models.Model):
    _name = "real.estate.project"
    _description = "Real Estate Project"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Short code used in unit codes, e.g. HNC.")
    location = fields.Char()
    expected_delivery_date = fields.Date()
    active = fields.Boolean(default=True)
    # Odoo hygiene: every model carries its company and currency.
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")

    # BR-01 style: codes are unique inside a company (units use the same rule).
    _code_company_unique = models.Constraint(
        "UNIQUE (company_id, code)",
        "A project code must be unique within its company.",
    )
