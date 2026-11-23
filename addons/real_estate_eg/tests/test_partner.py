from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestPartnerIdentity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        agent = new_test_user(
            cls.env, login="re_agent", groups="real_estate_eg.group_real_estate_agent"
        )
        # Agents create customers (BR-35), so the test runs as one.
        cls.Partner = cls.env["res.partner"].with_user(agent)

    def _create(self, national_id):
        return self.Partner.create(
            {
                "name": "Fictional Buyer",
                "nationality": "egyptian",
                "national_id": national_id,
            }
        )

    # Today frozen, so the "born in the future" case stays in the future.
    @freeze_time("2027-01-10")
    def test_ac_01_4_national_id(self):
        """AC-01.4 / BR-06: national ID format and date of birth."""
        accepted = {
            "29901158800017": "AC-01.4: born 15 Jan 1999",
            "30002298800017": "29 Feb 2000, a leap year",
            "32701108800017": "born today",
        }
        for national_id, case in accepted.items():
            with self.subTest(case):
                self.assertEqual(self._create(national_id).national_id, national_id)

        refused = {
            "19901158800017": "AC-01.4: first digit 1",
            "29902308800017": "AC-01.4: 30 February",
            "33001018800017": "AC-01.4: born 1 Jan 2030, in the future",
            "49901158800017": "first digit 4",
            "30102298800017": "29 Feb 2001, not a leap year",
            "32701118800017": "born tomorrow",
            "2990115880001": "13 digits",
            "299011588000170": "15 digits",
            "2990115880001A": "a letter",
            "٢٩٩٠١١٥٨٨٠٠٠١٧": "Arabic-Indic digits",
        }
        for national_id, case in refused.items():
            with self.subTest(case), self.assertRaises(ValidationError):
                self._create(national_id)
