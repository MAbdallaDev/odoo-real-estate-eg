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

    # BR-46 in the database: one contact per national ID and per passport
    # number, so two saves at the same moment cannot both pass. Empty values
    # are left out of the index.
    _national_id_unique = models.UniqueIndex(
        "(national_id) WHERE national_id IS NOT NULL AND national_id != ''",
        "This national ID already belongs to another contact.",
    )
    _passport_number_unique = models.UniqueIndex(
        "(passport_number) WHERE passport_number IS NOT NULL AND passport_number != ''",
        "This passport number already belongs to another contact.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_identity_free(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("national_id") or vals.get("passport_number"):
            # One number written on several contacts would share it too.
            self._check_identity_free([vals] * len(self))
        return super().write(vals)

    def _check_identity_free(self, vals_list):
        """BR-46: a clear message naming the contact that already has the
        number. It runs before the INSERT / UPDATE: after it, the unique index
        would refuse first, with no contact name (an @api.constrains runs too
        late). Same search as Odoo's duplicate tax ID warning
        (_compute_same_vat_partner_id): sudo() and active_test=False, so a
        contact in another company or an archived one still counts."""
        Partner = self.with_context(active_test=False).sudo()
        for field in ("national_id", "passport_number"):
            numbers = [vals[field] for vals in vals_list if vals.get(field)]
            if not numbers:
                continue
            if len(numbers) != len(set(numbers)):
                raise ValidationError(
                    self.env._("Two contacts cannot share one identity number.")
                )
            other = Partner.search(
                [(field, "in", numbers), ("id", "not in", self.ids)], limit=1
            )
            if not other:
                continue
            if field == "national_id":
                message = self.env._(
                    "The national ID %(number)s already belongs to %(contact)s.",
                    number=other.national_id,
                    contact=other.display_name,
                )
            else:
                message = self.env._(
                    "The passport number %(number)s already belongs to %(contact)s.",
                    number=other.passport_number,
                    contact=other.display_name,
                )
            raise ValidationError(message)

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
