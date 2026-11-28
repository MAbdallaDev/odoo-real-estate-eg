from odoo import fields, models


class RealEstateReservation(models.Model):
    """BR-57: the identity a customer types with a portal request. Kept on the
    request, not written to the contact: the agent checks it against the card
    when they call the customer and copies it to the contact (BR-05, BR-06),
    so the portal never edits contacts and never says whether a number is
    already known."""

    _inherit = "real.estate.reservation"

    customer_nationality = fields.Selection(
        [("egyptian", "Egyptian"), ("foreign", "Foreign")],
        string="Nationality (portal)",
        readonly=True,
        copy=False,
    )
    customer_national_id = fields.Char(
        string="National ID (portal)", readonly=True, copy=False
    )
    customer_passport_number = fields.Char(
        string="Passport Number (portal)", readonly=True, copy=False
    )
