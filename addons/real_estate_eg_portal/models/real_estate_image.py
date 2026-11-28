from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RealEstateImage(models.Model):
    """BR-61 (US-17): one photo of a project or of a unit, shown on the
    customer portal. Staff upload them on the project and unit forms; the
    first one by sequence is the cover. The sizes (1920, 1024, 512, 256, 128)
    come from image.mixin."""

    _name = "real.estate.image"
    _description = "Real Estate Photo"
    _inherit = ["image.mixin"]
    _order = "sequence, id"

    name = fields.Char(string="Caption")
    sequence = fields.Integer(default=10)
    image_1920 = fields.Image(required=True)
    project_id = fields.Many2one(
        "real.estate.project", index="btree_not_null", ondelete="cascade"
    )
    unit_id = fields.Many2one(
        "real.estate.unit", index="btree_not_null", ondelete="cascade"
    )
    company_id = fields.Many2one(
        "res.company", compute="_compute_company_id", store=True, index=True
    )

    @api.depends("project_id.company_id", "unit_id.company_id")
    def _compute_company_id(self):
        for image in self:
            image.company_id = image.unit_id.company_id or image.project_id.company_id

    # image_1920 is always written on create, so the check also runs when
    # neither owner is given (Odoo checks only the fields written).
    @api.constrains("project_id", "unit_id", "image_1920")
    def _check_owner(self):
        for image in self:
            if bool(image.project_id) == bool(image.unit_id):
                raise ValidationError(
                    self.env._("A photo belongs to one project or to one unit.")
                )


class RealEstateProject(models.Model):
    """BR-61 / BR-62: what the portal shows about a project."""

    _inherit = "real.estate.project"

    image_ids = fields.One2many("real.estate.image", "project_id", string="Photos")
    portal_description = fields.Html(
        string="Description (portal)",
        translate=True,
        help="Shown to customers on the unit page: area, buildings, services, "
        "transport…",
    )
    # BR-62: the plans this project is sold with, shown to customers on the
    # unit page, worked out on the unit's price.
    plan_template_ids = fields.Many2many(
        "real.estate.plan.template",
        relation="real_estate_project_plan_template_rel",
        column1="project_id",
        column2="plan_template_id",
        string="Plans Offered",
        help="The payment plans customers see on this project's unit pages.",
    )


class RealEstateUnit(models.Model):
    """BR-61: the unit's own photos and floor plan. A unit without photos
    shows its project's."""

    _inherit = "real.estate.unit"

    image_ids = fields.One2many("real.estate.image", "unit_id", string="Photos")
    floor_plan = fields.Image(max_width=1920, max_height=1920)

    def _portal_images(self):
        """BR-61: the unit's photos, else its project's."""
        self.ensure_one()
        return self.image_ids or self.project_id.image_ids
