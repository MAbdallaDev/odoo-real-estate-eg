"""Tests for the schedule arithmetic, written BEFORE the code (Story 03, Step 4).

compute_schedule() is a pure function, so these tests need no database
(BaseCase, as core does for pure helpers, e.g. html_editor's diff_utils).
Expected numbers come from docs/business-requirements.md §6.6, Examples A-C.
Expected dates are written out, not computed with relativedelta, so the test
does not repeat the code it checks.
"""

from datetime import date

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.real_estate_eg.tools.schedule import compute_schedule

# §6.3 plans, as compute_schedule() arguments (without price and date).
NH_STD_8Q = {
    "down_payment_percent": 10,
    "installment_count": 32,
    "step_months": 3,
    "first_installment_months": 3,
    "maintenance_percent": 8,
    "maintenance_at_signing": False,
}
NH_EXT_10Q = dict(NH_STD_8Q, down_payment_percent=5, installment_count=40)
NH_SAHEL_7Q = dict(NH_STD_8Q, installment_count=28, maintenance_percent=10)
NH_BIZ_5M = {
    "down_payment_percent": 20,
    "installment_count": 60,
    "step_months": 1,
    "first_installment_months": 1,
    "maintenance_percent": 10,
    "maintenance_at_signing": True,
}
NH_CASH = {
    "down_payment_percent": 100,
    "installment_count": 0,
    "step_months": 0,
    "first_installment_months": 0,
    "maintenance_percent": 8,
    "maintenance_at_signing": False,
}


def line(line_type, amount, date_due, number=0):
    return {
        "line_type": line_type,
        "number": number,
        "amount": amount,
        "date_due": date_due,
    }


def of_type(lines, line_type):
    return [row for row in lines if row["line_type"] == line_type]


@tagged("post_install", "-at_install")
class TestScheduleMath(BaseCase):
    def test_ac_02_1_example_a(self):
        """AC-02.1 / Example A: 8,580,000 on NH-STD-8Q, 10 Jan 2027."""
        lines = compute_schedule(8_580_000, date(2027, 1, 10), **NH_STD_8Q)

        # Quarterly on the 10th from April 2027: Apr, Jul, Oct, Jan...
        due_dates = [
            date(2027 + (3 + 3 * k) // 12, (3 + 3 * k) % 12 + 1, 10) for k in range(32)
        ]
        self.assertEqual(due_dates[0], date(2027, 4, 10))
        self.assertEqual(due_dates[30], date(2034, 10, 10))
        self.assertEqual(due_dates[31], date(2035, 1, 10))
        expected = (
            [line("down_payment", 858_000, date(2027, 1, 10))]
            + [
                line("installment", 241_313, due_dates[k - 1], number=k)
                for k in range(1, 32)
            ]
            + [line("installment", 241_297, date(2035, 1, 10), number=32)]
            # BR-18: due at delivery, so no date yet.
            + [line("maintenance", 686_400, None)]
        )
        self.assertEqual(lines, expected)
        for row in lines:
            self.assertIsInstance(row["amount"], int, "whole EGP as int")

    def test_ac_02_2_example_b_sums_to_price(self):
        """AC-02.2 / Example B: down payment + installments = the price, to the
        pound, for an ugly price and for any price and plan."""
        lines = compute_schedule(6_712_345, date(2027, 1, 10), **NH_STD_8Q)
        installments = of_type(lines, "installment")
        self.assertEqual(of_type(lines, "down_payment")[0]["amount"], 671_235)
        self.assertEqual(len(installments), 32)
        self.assertEqual({row["amount"] for row in installments[:31]}, {188_785})
        self.assertEqual(installments[31]["amount"], 188_775)

        plans = {
            "NH-STD-8Q": NH_STD_8Q,
            "NH-EXT-10Q": NH_EXT_10Q,
            "NH-SAHEL-7Q": NH_SAHEL_7Q,
            "NH-BIZ-5M": NH_BIZ_5M,
            "NH-CASH": NH_CASH,
        }
        prices = [8_580_000, 6_712_345, 3_660_000, 1_000_001, 12_345_679, 2_999_999]
        for code, plan in plans.items():
            for price in prices:
                with self.subTest(plan=code, price=price):
                    lines = compute_schedule(price, date(2027, 1, 31), **plan)
                    total = sum(
                        row["amount"]
                        for row in lines
                        if row["line_type"] != "maintenance"
                    )
                    self.assertEqual(total, price)
                    installments = of_type(lines, "installment")
                    self.assertEqual(len(installments), plan["installment_count"])
                    self.assertEqual(
                        [row["number"] for row in installments],
                        list(range(1, plan["installment_count"] + 1)),
                    )
                    # All installments but the last are equal (BR-16).
                    self.assertLessEqual(
                        len({row["amount"] for row in installments[:-1]}), 1
                    )

    def test_ac_02_3_example_c_month_end(self):
        """AC-02.3 / Example C: NH-BIZ-5M on 31 Jan 2027. Dates come from the
        contract date every time, so day 31 comes back after short months."""
        lines = compute_schedule(3_660_000, date(2027, 1, 31), **NH_BIZ_5M)
        installments = of_type(lines, "installment")
        self.assertEqual(
            [row["date_due"] for row in installments[:4]],
            [
                date(2027, 2, 28),
                date(2027, 3, 31),
                date(2027, 4, 30),
                date(2027, 5, 31),
            ],
        )
        # 2028 is a leap year: 31 Jan 2027 + 13 months = 29 Feb 2028.
        self.assertEqual(installments[12]["date_due"], date(2028, 2, 29))
        self.assertEqual(installments[59]["date_due"], date(2032, 1, 31))
        self.assertEqual({row["amount"] for row in installments}, {48_800})
        self.assertEqual(
            of_type(lines, "down_payment"),
            [line("down_payment", 732_000, date(2027, 1, 31))],
        )
        # BR-18: due at signing, so on the contract date.
        self.assertEqual(
            of_type(lines, "maintenance"),
            [line("maintenance", 366_000, date(2027, 1, 31))],
        )

    def test_ac_02_4_cash_plan(self):
        """AC-02.4 / BR-20: NH-CASH is one down payment of the full price and
        no installments; the deposit is still its own line."""
        lines = compute_schedule(8_580_000, date(2027, 1, 10), **NH_CASH)
        self.assertEqual(
            lines,
            [
                line("down_payment", 8_580_000, date(2027, 1, 10)),
                line("maintenance", 686_400, None),
            ],
        )
        # A deposit of 0 % is left out, as is a down payment of 0 %.
        no_deposit = dict(NH_STD_8Q, down_payment_percent=0, maintenance_percent=0)
        lines = compute_schedule(8_580_000, date(2027, 1, 10), **no_deposit)
        self.assertEqual({row["line_type"] for row in lines}, {"installment"})

    def test_br_45_half_up_ties(self):
        """BR-45: exact decimal arithmetic, half up to whole EGP. Python's
        round() gives 858,000 (half to even); a float can hide the .5."""
        # 8,580,005 x 10 % = 858,000.5: half up gives 858,001.
        lines = compute_schedule(8_580_005, date(2027, 1, 10), **NH_STD_8Q)
        self.assertEqual(of_type(lines, "down_payment")[0]["amount"], 858_001)
        # In float, 1,310,730 x 0.35 = 458755.49999999994; exact is 458,755.5.
        plan = dict(NH_STD_8Q, down_payment_percent=35)
        lines = compute_schedule(1_310_730, date(2027, 1, 10), **plan)
        self.assertEqual(of_type(lines, "down_payment")[0]["amount"], 458_756)
        # Example A's installment tie: 7,722,000 / 32 = 241,312.5 -> 241,313.
        lines = compute_schedule(8_580_000, date(2027, 1, 10), **NH_STD_8Q)
        self.assertEqual(of_type(lines, "installment")[0]["amount"], 241_313)
        # Deposit tie: 6,712,345 x 10 % = 671,234.5 -> 671,235.
        lines = compute_schedule(6_712_345, date(2027, 1, 10), **NH_SAHEL_7Q)
        self.assertEqual(of_type(lines, "maintenance")[0]["amount"], 671_235)
