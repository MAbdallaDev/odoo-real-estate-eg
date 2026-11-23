from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestContract(RealEstateCommon):
    def test_ac_01_1_create_reserves_unit(self):
        """AC-01.1 / US-01, BR-07, BR-08: draft, sequence reference, frozen price."""
        contract = self.create_contract()
        self.assertEqual(contract.state, "draft")
        self.assertRegex(contract.name, r"^NH/\d{4}/\d{5}$")
        self.assertEqual(contract.price, 8_580_000)
        # The unit showing "reserved" is added with the unit status (Step 6).

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
