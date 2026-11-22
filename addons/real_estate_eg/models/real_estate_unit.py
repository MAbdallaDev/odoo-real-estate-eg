from odoo import api, fields, models


class RealEstateUnit(models.Model):
    _name = "real.estate.unit"
    _description = "Real Estate Unit"
    _rec_name = "code"
    _order = "code"

    code = fields.Char(
        required=True, help="e.g. HNC-B07-0302: project, building, floor, unit."
    )
    # BR-01: a unit belongs to exactly one project.
    project_id = fields.Many2one(
        "real.estate.project", required=True, index=True, ondelete="restrict"
    )
    # BR-02: type, area, floor and list price.
    unit_type = fields.Selection(
        [
            ("apartment", "Apartment"),
            ("duplex", "Duplex"),
            ("chalet", "Chalet"),
            ("twin_house", "Twin House"),
            ("office", "Office"),
            ("retail", "Retail"),
        ],
        string="Type",
        required=True,
    )
    bedrooms = fields.Integer()
    area = fields.Float(string="Area (m²)", required=True)
    floor = fields.Integer()
    list_price = fields.Monetary(required=True)
    # BR-02: price per m² is shown, computed from list price ÷ area.
    price_per_sqm = fields.Monetary(
        string="Price per m²", compute="_compute_price_per_sqm"
    )
    active = fields.Boolean(default=True)
    # The unit's company always follows its project's company.
    company_id = fields.Many2one(
        related="project_id.company_id", store=True, index=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id")

    # BR-01: a unit's code is unique within its company.
    _code_company_unique = models.Constraint(
        "UNIQUE (company_id, code)",
        "A unit code must be unique within its company.",
    )
    _area_positive = models.Constraint("CHECK (area > 0)", "The area must be positive.")
    _list_price_not_negative = models.Constraint(
        "CHECK (list_price >= 0)", "The list price cannot be negative."
    )

    @api.depends("list_price", "area")
    def _compute_price_per_sqm(self):
        for unit in self:
            unit.price_per_sqm = unit.list_price / unit.area if unit.area else 0.0
