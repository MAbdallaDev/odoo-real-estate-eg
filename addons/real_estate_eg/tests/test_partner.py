from freezegun import freeze_time
from psycopg2.errors import UniqueViolation

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


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

    def test_br_46_identity_unique(self):
        """BR-46: a national ID or passport number belongs to one contact only,
        across all companies, archived contacts included."""
        first = self._create("29901158800017")
        foreign = self.Partner.create(
            {
                "name": "Fictional Buyer Foreign",
                "nationality": "foreign",
                "passport_number": "X1234567",
            }
        )

        # A second contact with the same number is refused, naming the first.
        with self.assertRaises(ValidationError) as caught:
            self._create("29901158800017")
        self.assertIn(first.name, str(caught.exception))
        with self.assertRaises(ValidationError) as caught:
            self.Partner.create(
                {
                    "name": "Another Buyer",
                    "nationality": "foreign",
                    "passport_number": "X1234567",
                }
            )
        self.assertIn(foreign.name, str(caught.exception))

        # Saving a contact again with its own number is fine.
        first.write(
            {"name": "Fictional Buyer Renamed", "national_id": "29901158800017"}
        )

        # Contacts the agent cannot see still count (sudo, active_test=False).
        other_company = self.env["res.company"].create(
            {"name": "Fictional Other Developer"}
        )
        self.env["res.partner"].create(
            {
                "name": "Other Company Buyer",
                "company_id": other_company.id,
                "nationality": "egyptian",
                "national_id": "29901158800025",
            }
        )
        archived = self.env["res.partner"].create(
            {
                "name": "Archived Buyer",
                "nationality": "egyptian",
                "national_id": "29901158800033",
            }
        )
        archived.action_archive()
        for national_id, owner in (
            ("29901158800025", "Other Company Buyer"),
            ("29901158800033", "Archived Buyer"),
        ):
            with self.subTest(owner), self.assertRaises(ValidationError) as caught:
                self._create(national_id)
            self.assertIn(owner, str(caught.exception))

        # The database refuses a duplicate even when the Python check is
        # skipped, as in two saves at the same moment.
        second = self._create("29901158800041")
        self.env.flush_all()
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.env.cr.execute(
                "UPDATE res_partner SET national_id = %s WHERE id = %s",
                [first.national_id, second.id],
            )
