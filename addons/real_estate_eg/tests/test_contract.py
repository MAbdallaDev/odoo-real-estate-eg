from psycopg2.errors import UniqueViolation

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestContract(RealEstateCommon):
    def test_ac_01_1_create_reserves_unit(self):
        """AC-01.1 / US-01, BR-03, BR-07, BR-08: draft, sequence reference,
        frozen price, and the unit shows reserved."""
        self.assertEqual(self.unit_3br.state, "available")
        contract = self.create_contract()
        self.assertEqual(contract.state, "draft")
        self.assertRegex(contract.name, r"^NH/\d{4}/\d{5}$")
        self.assertEqual(contract.price, 8_580_000)
        self.assertEqual(self.unit_3br.state, "reserved")

    def test_ac_01_2_price_frozen(self):
        """AC-01.2 / BR-08: a later list price change does not reach the contract."""
        contract = self.create_contract()
        self.unit_3br.with_user(self.manager).list_price = 9_000_000
        self.env.flush_all()
        contract.invalidate_recordset()  # read again from the database
        self.assertEqual(contract.price, 8_580_000)

    def test_ac_01_6_unit_change_retakes_price(self):
        """AC-01.6 / BR-08: changing the unit on a draft re-takes the price."""
        contract = self.create_contract()
        contract.with_user(self.agent_a).unit_id = self.unit_2br
        self.assertEqual(contract.price, 6_500_000)

    def test_ac_01_3_second_contract_refused(self):
        """AC-01.3 / BR-04: refused for anyone, in any order; the message gives
        the existing contract's reference only."""
        first = self.create_contract(user=self.agent_a)
        for user in (self.agent_b, self.manager, self.agent_a):
            with (
                self.subTest(user=user.login),
                self.assertRaises(ValidationError) as error,
            ):
                self.create_contract(user=user, partner=self.customer_foreign)
            self.assertIn(first.name, str(error.exception))
            self.assertNotIn(self.customer_eg.name, str(error.exception))

        # Other order: a manager sells first, an agent is refused.
        self.create_contract(user=self.manager, unit=self.unit_2br)
        with self.assertRaises(ValidationError):
            self.create_contract(user=self.agent_b, unit=self.unit_2br)

        # Moving a draft onto a taken unit is refused too.
        unit_free = self.unit_2br.copy({"code": "HNC-B07-0303"})
        draft = self.create_contract(unit=unit_free)
        with self.assertRaises(ValidationError):
            draft.with_user(self.agent_a).unit_id = self.unit_3br

        # Two new contracts for one free unit in the same save.
        unit_new = unit_free.copy({"code": "HNC-B07-0304"})
        vals = {"partner_id": self.customer_eg.id, "unit_id": unit_new.id}
        with self.assertRaisesRegex(ValidationError, "cannot share one unit"):
            self.env["real.estate.contract"].with_user(self.manager).create(
                [vals, vals]
            )

    def test_ac_01_3_database_blocks_double_sale(self):
        """BR-04 in the database: the unique index refuses a second live
        contract even when the Python check is skipped, as in two saves at the
        same moment."""
        first = self.create_contract()
        first.state = "cancelled"  # until Step 11 adds the cancel action
        self.create_contract(user=self.agent_b)
        self.env.flush_all()
        # The database logs the refused query as ERROR; mute it for the log check.
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.env.cr.execute(
                "UPDATE real_estate_contract SET state = 'draft' WHERE id = %s",
                [first.id],
            )

    def test_cancelled_contract_frees_unit_for_resale(self):
        """BR-04: a cancelled contract does not block the unit."""
        first = self.create_contract()
        first.state = "cancelled"  # until Step 11 adds the cancel action
        self.assertEqual(self.unit_3br.state, "available")
        second = self.create_contract(user=self.agent_b)
        self.assertEqual(second.state, "draft")
        self.assertEqual(self.unit_3br.state, "reserved")

    def test_ac_01_5_delete_draft_only(self):
        """AC-01.5 / BR-13: a draft can be deleted and frees the unit; a
        confirmed contract cannot be deleted, by anyone."""
        draft = self.create_contract()
        draft.with_user(self.agent_a).unlink()
        self.assertEqual(self.unit_3br.state, "available")

        confirmed = self.create_contract()
        confirmed.state = "confirmed"  # until Step 9 adds the confirm action
        for user in (self.agent_a, self.manager):
            with (
                self.subTest(user=user.login),
                self.assertRaisesRegex(UserError, "Only draft contracts"),
            ):
                confirmed.with_user(user).unlink()

    def test_br_35_agent_edits_only_drafts(self):
        """BR-35: an agent edits a contract only while draft; a manager can
        edit it later, but nobody changes its unit once it is confirmed."""
        contract = self.create_contract()
        contract.with_user(self.agent_a).date = "2027-01-10"  # draft: allowed
        contract.state = "confirmed"  # until Step 9 adds the confirm action

        with self.assertRaises(AccessError):
            contract.with_user(self.agent_a).date = "2027-01-11"
        contract.with_user(self.manager).date = "2027-01-11"
        with self.assertRaisesRegex(UserError, "only on a draft"):
            contract.with_user(self.manager).unit_id = self.unit_2br
