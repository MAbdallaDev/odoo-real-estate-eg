import re
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # BR-05: nationality is its own field; the address country does not say it.
    nationality = fields.Selection([("egyptian", "Egyptian"), ("foreign", "Foreign")])
    national_id = fields.Char(string="National ID", copy=False)
    passport_number = fields.Char(copy=False)

    @api.constrains("national_id")
    def _check_national_id(self):
        for partner in self:
            if partner.national_id and not partner._is_valid_national_id(
                partner.national_id
            ):
                raise ValidationError(
                    self.env._(
                        "The national ID %(national_id)s is not valid.",
                        national_id=partner.national_id,
                    )
                )

    def _is_valid_national_id(self, national_id):
        """BR-06: 14 digits, first digit 2 (1900s) or 3 (2000s), then a real
        date of birth YYMMDD that is not in the future."""
        # [0-9], not \d: \d also matches Arabic-Indic digits.
        if not re.fullmatch(r"[23][0-9]{13}", national_id):
            return False
        century = 1900 if national_id[0] == "2" else 2000
        try:
            birth_date = date(
                century + int(national_id[1:3]),
                int(national_id[3:5]),
                int(national_id[5:7]),
            )
        except ValueError:  # e.g. 30 February
            return False
        return birth_date <= fields.Date.context_today(self)
