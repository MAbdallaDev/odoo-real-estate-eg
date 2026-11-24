from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestSchedule(RealEstateCommon):
    def test_br_19_schedule_lines_locked(self):
        """BR-19 / BR-18: lines change only on a draft, for everyone; the total
        leaves the maintenance deposit out."""
        contract = self.create_contract()
        Line = self.env["real.estate.installment"].with_user(self.agent_a)
        lines = Line.create(
            [
                {
                    "contract_id": contract.id,
                    "line_type": "down_payment",
                    "amount": 8_580_000,
                    "date_due": "2027-01-10",
                },
                {
                    "contract_id": contract.id,
                    "line_type": "maintenance",
                    "amount": 686_400,
                },
            ]
        )
        self.assertEqual(contract.schedule_total, 8_580_000)
        self.assertEqual(lines[0].name, "Down Payment")

        contract.with_user(self.manager).action_confirm()
        for user in (self.agent_a, self.manager):
            with self.subTest(user=user.login):
                with self.assertRaises(UserError):
                    lines[0].with_user(user).write({"amount": 1})
                with self.assertRaises(UserError):
                    lines[1].with_user(user).unlink()
                with self.assertRaises(UserError):
                    Line.with_user(user).create(
                        {
                            "contract_id": contract.id,
                            "line_type": "installment",
                            "number": 1,
                            "amount": 1,
                        }
                    )
        # The superuser passes (Story 04's nightly job).
        lines[1].sudo().write({"date_due": "2027-06-30"})

    def _contract_on(self, day, unit=None):
        """A draft contract of agent A dated `day`."""
        contract = self.create_contract(unit=unit)
        contract.with_user(self.agent_a).write({"date": day})
        return contract

    def test_ac_02_1_generate_from_wizard(self):
        """AC-02.1: the agent generates Example A through the dialog."""
        contract = self._contract_on(date(2027, 1, 10))
        self.generate_schedule(contract, self.plan_std)

        self.assertEqual(contract.plan_id, self.plan_std)
        self.assertEqual(len(contract.installment_ids), 34)
        down, *installments, deposit = contract.installment_ids
        self.assertEqual(
            (down.line_type, down.amount, down.date_due),
            ("down_payment", 858_000, date(2027, 1, 10)),
        )
        self.assertEqual(len(installments), 32)
        self.assertEqual({line.amount for line in installments[:31]}, {241_313})
        self.assertEqual(installments[-1].amount, 241_297)
        self.assertEqual(installments[-1].name, "Installment 32")
        self.assertEqual(installments[0].date_due, date(2027, 4, 10))
        self.assertEqual(installments[-1].date_due, date(2035, 1, 10))
        # BR-18: due at delivery, so no date yet; not part of the price.
        self.assertEqual(
            (deposit.line_type, deposit.amount, deposit.date_due),
            ("maintenance", 686_400, False),
        )
        self.assertEqual(contract.schedule_total, contract.price)

    def test_ac_02_4_generate_cash_plan(self):
        """AC-02.4: NH-CASH gives one down payment of the full price."""
        contract = self._contract_on(date(2027, 1, 10))
        self.generate_schedule(contract, self.plan_cash)
        self.assertEqual(
            [(line.line_type, line.amount) for line in contract.installment_ids],
            [("down_payment", 8_580_000), ("maintenance", 686_400)],
        )

    def test_ac_02_5_regenerate_draft_only(self):
        """AC-02.5 / BR-19: another plan replaces a draft's lines; once
        confirmed, nobody can regenerate."""
        contract = self._contract_on(date(2026, 1, 31))
        self.generate_schedule(contract, self.plan_std)
        old_ids = contract.installment_ids.ids
        self.generate_schedule(contract, self.plan_biz)

        Line = self.env["real.estate.installment"]
        self.assertFalse(Line.browse(old_ids).exists())
        self.assertEqual(contract.plan_id, self.plan_biz)
        self.assertEqual(len(contract.installment_ids), 62)  # down + 60 + deposit
        self.assertEqual(contract.installment_ids[1].date_due, date(2026, 2, 28))

        contract.with_user(self.manager).action_confirm()
        # Confirmation writes the same date again: the lines stay.
        self.assertEqual(len(contract.installment_ids), 62)
        for user in (self.agent_a, self.manager):
            with self.subTest(user=user.login):
                with self.assertRaises(UserError):
                    contract.with_user(user).action_generate_schedule()
                with self.assertRaises(UserError):
                    contract.with_user(user)._generate_schedule(self.plan_std)
        self.assertEqual(contract.plan_id, self.plan_biz)

    def test_stale_schedule_dropped(self):
        """A new date or unit (so price) on a draft deletes its schedule, so
        an old schedule can never be confirmed by mistake."""
        contract = self._contract_on(date(2027, 1, 10))
        agent_contract = contract.with_user(self.agent_a)
        self.generate_schedule(contract, self.plan_std)
        agent_contract.write({"date": date(2027, 1, 10)})  # same date: kept
        self.assertEqual(len(contract.installment_ids), 34)

        agent_contract.write({"date": date(2027, 2, 1)})
        self.assertFalse(contract.installment_ids)

        self.generate_schedule(contract, self.plan_std)
        agent_contract.write({"unit_id": self.unit_2br.id})
        self.assertFalse(contract.installment_ids)
        self.assertEqual(contract.price, 6_500_000)

    def test_generate_refusals(self):
        """No contract date (BR-17), or a price too small for the plan (a last
        installment of 0 or less), refuses the generation."""
        with self.assertRaises(UserError):
            self.generate_schedule(self.create_contract(), self.plan_std)

        # 2,065 on NH-BIZ-5M: down 413, 59 x 28 = 1,652 = the whole rest, last 0.
        tiny = self.make_unit("HNC-TINY")
        tiny.list_price = 2_065
        contract = self._contract_on(date(2027, 1, 31), unit=tiny)
        with self.assertRaises(UserError):
            self.generate_schedule(contract, self.plan_biz)
        self.assertFalse(contract.installment_ids)
