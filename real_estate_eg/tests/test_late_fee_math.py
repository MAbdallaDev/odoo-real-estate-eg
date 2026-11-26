"""Tests for the late-fee arithmetic, written before the code (Story 05, Step 2).

The functions are pure (no database), so the tests run on BaseCase, like
test_schedule_math.py. Expected numbers come from docs/business-requirements.md
§6.6, Example D, written out by hand so the test does not repeat the code.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.real_estate_eg.tools.late_fee import (
    compute_late_fee,
    days_past_due,
    paid_date,
)
from odoo.addons.real_estate_eg.tools.schedule import half_up

# §6.4 policy: 1% a month, capped at 10%, 7 days of grace.
POLICY = {"monthly_rate": 1, "cap_percent": 10, "grace_days": 7}
DUE = date(2027, 4, 10)  # Example A, installment 1
AMOUNT = 241_313


def fee(payments, as_of, amount=AMOUNT, due=DUE):
    return compute_late_fee(amount, due, payments, as_of, **POLICY)


def piastres(value):
    """Shown on screen: half up to 0.01 (BR-27)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@tagged("post_install", "-at_install")
class TestLateFeeMath(BaseCase):
    def test_example_d_paid_in_full(self):
        """AC-05.2 / AC-05.8: 45 days (10 Apr - 24 May) x 241,313 x 1% / 30
        = 3,619.695 -> shown 3,619.70 -> billed 3,620; never 3,619.80."""
        result = fee([(date(2027, 5, 25), AMOUNT)], date(2027, 5, 25))
        self.assertEqual(result, Decimal("3619.695"))
        self.assertEqual(piastres(result), Decimal("3619.70"))
        self.assertEqual(half_up(result), 3620)
        # Rounding each day to 80.44 would drift to 3,619.80.
        self.assertNotEqual(piastres(result), 45 * Decimal("80.44"))
        # Once paid, a later as-of date changes nothing.
        self.assertEqual(fee([(date(2027, 5, 25), AMOUNT)], date(2027, 9, 1)), result)

    def test_example_d_paid_in_two_parts(self):
        """AC-05.3: 20 days on 241,313 + 25 days on 100,000 = 2,442.0867
        -> shown 2,442.09 -> billed 2,442. A payment counts from its own date."""
        payments = [(date(2027, 4, 30), 141_313), (date(2027, 5, 25), 100_000)]
        result = fee(payments, date(2027, 5, 25))
        expected = (Decimal(20 * 241_313) + Decimal(25 * 100_000)) / Decimal(3000)
        self.assertEqual(result, expected)
        self.assertEqual(piastres(result), Decimal("2442.09"))
        self.assertEqual(half_up(result), 2442)

    def test_grace_forgives_only_inside_it(self):
        """BR-26 / BR-27: paid on day 8 after the due date -> never overdue,
        no fee. Paid on day 9 -> it was overdue on day 8 -> 9 days, counted
        from the due date, not from the end of grace."""
        self.assertEqual(fee([(date(2027, 4, 18), AMOUNT)], date(2027, 5, 1)), 0)
        self.assertEqual(
            fee([(date(2027, 4, 19), AMOUNT)], date(2027, 5, 1)),
            Decimal(9 * AMOUNT) / Decimal(3000),
        )

    def test_unpaid_as_of(self):
        """AC-05.1: unpaid on 17 Apr (due + 7) -> not overdue, no fee yet; on
        18 Apr -> overdue, 8 days so far (the as-of day itself is not counted).
        A payment dated after the as-of date is not known yet."""
        self.assertEqual(fee([], date(2027, 4, 17)), 0)
        self.assertEqual(fee([], date(2027, 4, 18)), Decimal(8 * AMOUNT) / 3000)
        self.assertEqual(
            fee([(date(2027, 5, 25), AMOUNT)], date(2027, 5, 1)),
            Decimal(21 * AMOUNT) / 3000,
        )
        self.assertEqual(days_past_due(DUE, date(2027, 4, 17)), 7)
        self.assertEqual(days_past_due(DUE, date(2027, 4, 18)), 8)
        self.assertEqual(days_past_due(DUE, date(2027, 4, 1)), 0)

    def test_cap(self):
        """AC-05.5 / BR-28: never above 10% of the line: 24,131.30."""
        self.assertEqual(fee([], date(2028, 5, 14)), Decimal("24131.3"))
        self.assertEqual(fee([], date(2030, 1, 1)), Decimal("24131.3"))
        # 300 days x 241,313 / 3000 = exactly the cap; 299 days is under it.
        self.assertEqual(fee([], DUE + timedelta(days=300)), Decimal("24131.3"))
        self.assertEqual(
            fee([], DUE + timedelta(days=299)), Decimal(299 * AMOUNT) / 3000
        )

    def test_confirmed_late(self):
        """AC-05.10: dated 10 Jan, confirmed 30 Jan 2027 -> effective due date
        30 Jan. Not overdue on 6 Feb; nothing charged for 10-29 Jan."""
        due = date(2027, 1, 30)
        self.assertEqual(days_past_due(due, date(2027, 2, 6)), 7)
        self.assertEqual(fee([], date(2027, 2, 6), 858_000, due), 0)
        # On 8 Feb it is overdue: 9 days, 30 Jan - 7 Feb.
        self.assertEqual(
            fee([], date(2027, 2, 8), 858_000, due), Decimal(9 * 858_000) / 3000
        )

    def test_paid_date(self):
        """The day cumulative payments reach the amount; None while short."""
        self.assertIsNone(paid_date(AMOUNT, [(date(2027, 4, 30), 141_313)]))
        self.assertEqual(
            paid_date(
                AMOUNT,
                [(date(2027, 5, 25), 100_000), (date(2027, 4, 30), 141_313)],
            ),
            date(2027, 5, 25),
        )
