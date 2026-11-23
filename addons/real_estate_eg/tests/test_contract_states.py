from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestContractStates(RealEstateCommon):
    def test_ac_10_1_only_manager_confirms(self):
        """AC-10.1 / US-10, BR-10: an agent cannot confirm; a manager can."""
        contract = self.create_contract()
        with self.assertRaises(AccessError):
            contract.with_user(self.agent_a).action_confirm()
        self.assertEqual(contract.state, "draft")

        contract.with_user(self.manager).action_confirm()
        today = fields.Date.context_today(contract)
        self.assertEqual(contract.state, "confirmed")
        self.assertEqual(contract.confirmation_date, today)
        self.assertEqual(contract.date, today)  # BR-07: empty date filled

    def test_ac_10_2_identity_required(self):
        """AC-10.2 / BR-05 (identity part): individuals need a national ID
        (Egyptian) or a passport number (foreign); a company needs neither.
        The schedule check is Story 03."""
        no_nationality = self.env["res.partner"].create({"name": "Fictional NoNat"})
        foreign_no_passport = self.env["res.partner"].create(
            {"name": "Fictional Foreign NoPass", "nationality": "foreign"}
        )
        refused = {
            "national ID": self.customer_eg_no_id,
            "passport number": foreign_no_passport,
            "nationality": no_nationality,
        }
        for number, (reason, partner) in enumerate(refused.items()):
            contract = self.create_contract(
                unit=self.make_unit(f"HNC-T-R{number}"), partner=partner
            )
            with self.subTest(reason), self.assertRaisesRegex(UserError, reason):
                contract.with_user(self.manager).action_confirm()

        accepted = (self.customer_eg, self.customer_foreign, self.customer_company)
        for number, partner in enumerate(accepted):
            contract = self.create_contract(
                unit=self.make_unit(f"HNC-T-A{number}"), partner=partner
            )
            with self.subTest(partner.name):
                contract.with_user(self.manager).action_confirm()
                self.assertEqual(contract.state, "confirmed")

    def test_ac_10_3_confirm_marks_unit_sold(self):
        """AC-10.3 (unit part) / BR-03: on confirmation the unit shows sold.
        Invoicing at confirmation is Story 04."""
        contract = self.create_contract()
        self.assertEqual(self.unit_3br.state, "reserved")
        contract.with_user(self.manager).action_confirm()
        self.assertEqual(self.unit_3br.state, "sold")

    def test_br_07_contract_date_not_after_confirmation(self):
        """BR-07: the contract date cannot be later than the confirmation day."""
        contract = self.create_contract()
        tomorrow = fields.Date.context_today(contract) + timedelta(days=1)
        contract.with_user(self.agent_a).date = tomorrow
        with self.assertRaisesRegex(UserError, "cannot be later"):
            contract.with_user(self.manager).action_confirm()

    def test_confirm_only_from_draft(self):
        """BR-09: no other transitions; a confirmed contract is not confirmed again."""
        contract = self.create_contract()
        contract.with_user(self.manager).action_confirm()
        with self.assertRaisesRegex(UserError, "Only a draft"):
            contract.with_user(self.manager).action_confirm()

    def test_ac_11_1_deliver_confirmed_by_manager_only(self):
        """AC-11.1 / US-11, BR-11: only a confirmed contract can be marked
        delivered, only by a manager; the date is recorded, the unit delivered."""
        contract = self.create_contract()
        with self.assertRaisesRegex(UserError, "Only a confirmed"):
            contract.with_user(self.manager).action_deliver()  # still draft

        contract.with_user(self.manager).action_confirm()
        with self.assertRaises(AccessError):
            contract.with_user(self.agent_a).action_deliver()
        self.assertEqual(contract.state, "confirmed")

        contract.with_user(self.manager).action_deliver()
        self.assertEqual(contract.state, "delivered")
        self.assertEqual(contract.delivery_date, fields.Date.context_today(contract))
        self.assertEqual(self.unit_3br.state, "delivered")  # BR-03

        with self.assertRaisesRegex(UserError, "Only a confirmed"):
            contract.with_user(self.manager).action_deliver()  # no second time

    def test_br_11_delivery_date(self):
        """BR-11: a manager may record an earlier handover date, never a future one."""
        contract = self.create_contract()
        contract.with_user(self.agent_a).date = "2026-01-10"
        contract.with_user(self.manager).action_confirm()
        today = fields.Date.context_today(contract)

        contract.with_user(self.manager).delivery_date = today + timedelta(days=1)
        with self.assertRaisesRegex(UserError, "in the future"):
            contract.with_user(self.manager).action_deliver()

        contract.with_user(self.manager).delivery_date = "2026-01-09"
        with self.assertRaisesRegex(UserError, "before the contract date"):
            contract.with_user(self.manager).action_deliver()

        contract.with_user(self.manager).delivery_date = "2026-02-01"
        contract.with_user(self.manager).action_deliver()
        self.assertEqual(str(contract.delivery_date), "2026-02-01")
