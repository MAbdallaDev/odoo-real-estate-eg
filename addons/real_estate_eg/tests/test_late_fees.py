from datetime import date

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestLateFees(RealEstateCommon):
    """US-05 / BR-26 - BR-31: overdue lines, late fees and the at-risk flag."""

    def test_settings_defaults(self):
        """T1. §6.4: 1% a month, capped at 10% of the line, 7 days of grace,
        at risk after 60 days; the Late Fee product carries no tax."""
        company = self.env.company
        self.assertEqual(company.re_late_fee_rate, 1)
        self.assertEqual(company.re_late_fee_cap, 10)
        self.assertEqual(company.re_grace_days, 7)
        self.assertEqual(company.re_at_risk_days, 60)
        product = self.env.ref("real_estate_eg.product_late_fee")
        self.assertFalse(product.taxes_id)
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.re_late_fee_account_id, self.late_fee_account)
        self.assertEqual(settings.re_grace_days, 7)

    # ------------------------------------------------------------------
    # Example D: Example A's installment 1, 241,313 due 10 Apr 2027.
    # ------------------------------------------------------------------

    def _installment_1_invoiced(self):
        """Example A confirmed on 10 Jan 2027; installment 1 invoiced on its
        due date, 10 Apr 2027 (so its effective due date is 10 Apr)."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
        with freeze_time("2027-04-10"):
            contract._invoice_due_lines(fields.Date.today())
        line = contract.installment_ids.filtered(lambda x: x.number == 1)
        return contract, line

    def _pay(self, line, amount, day, entered=None):
        """Register a payment dated `day`, entered on `entered` (default: the
        same day), through Odoo's register-payment wizard."""
        with freeze_time(entered or day):
            self._register_payment(
                line.sudo().invoice_id, amount=amount, payment_date=day
            )

    def test_payment_history(self):
        """T3. BR-24: each payment counts from its own date, even when it is
        entered later; the history is read from the invoice's reconciliation."""
        __, line = self._installment_1_invoiced()
        self.assertEqual(line._payment_history(), [])
        # Entered on 25 May, dated 30 Apr.
        self._pay(line, 141_313, "2027-04-30", entered="2027-05-25")
        self._pay(line, 100_000, "2027-05-25")
        self.assertEqual(
            line._payment_history(),
            [(date(2027, 4, 30), 141_313), (date(2027, 5, 25), 100_000)],
        )

    def _night(self, day):
        """The late-fee step of the nightly job, run for `day`."""
        with freeze_time(day):
            self.env["real.estate.installment"].search([])._recompute_late_fees(
                fields.Date.to_date(day)
            )

    def test_ac_05_1_overdue_after_grace(self):
        """T4. AC-05.1: not overdue on 15 and 17 Apr (due + 7), overdue on
        18 Apr. A payment clears the flag at once, before the next run."""
        contract, line = self._installment_1_invoiced()
        for day, days, overdue in (
            ("2027-04-15", 5, False),
            ("2027-04-17", 7, False),
            ("2027-04-18", 8, True),
        ):
            self._night(day)
            self.assertEqual(line.days_past_due, days, day)
            self.assertEqual(line.is_overdue, overdue, day)
        # Collections read it without rights on invoices.
        self.assertTrue(line.with_user(self.collections).is_overdue)
        self._pay(line, 241_313, "2027-04-20")
        self.assertFalse(line.is_overdue)

    def test_ac_05_2_example_d_full(self):
        """T5. AC-05.2 / AC-05.8: paid in full on 25 May -> 3,619.695 stored
        unrounded, shown 3,619.70 (not 3,619.80); the fee is final."""
        __, line = self._installment_1_invoiced()
        self._pay(line, 241_313, "2027-05-25")
        self._night("2027-05-25")
        self.assertEqual(line.late_fee_accrued, 3619.695)
        self.assertEqual(line.late_fee_unbilled, 3619.695)
        self.assertEqual(line.late_fee_display, 3619.70)
        self.assertNotEqual(line.late_fee_display, 3619.80)
        self.assertTrue(line.late_fee_final)
        self.assertEqual(line.days_past_due, 0)

    def test_ac_05_3_example_d_parts(self):
        """T5. AC-05.3: 141,313 on 30 Apr and 100,000 on 25 May -> 2,442.0867,
        shown 2,442.09."""
        __, line = self._installment_1_invoiced()
        self._pay(line, 141_313, "2027-04-30")
        self._night("2027-05-01")
        self.assertFalse(line.late_fee_final)
        self._pay(line, 100_000, "2027-05-25")
        self._night("2027-05-25")
        self.assertAlmostEqual(
            line.late_fee_accrued, (20 * 241_313 + 25 * 100_000) / 3000, places=9
        )
        self.assertEqual(line.late_fee_display, 2442.09)

    def test_ac_05_5_cap(self):
        """T6. AC-05.5: unpaid for 400 days -> capped at 10%: 24,131.30."""
        __, line = self._installment_1_invoiced()
        self._night("2028-05-14")
        self.assertEqual(line.late_fee_accrued, 24_131.3)

    def test_ac_05_10_confirmed_late(self):
        """T7. AC-05.10: dated 10 Jan 2027, confirmed 30 Jan 2027 -> the down
        payment's effective due date is 30 Jan: not overdue on 6 Feb, and once
        overdue its fee counts from 30 Jan, not 10 Jan."""
        with freeze_time("2027-01-30"):
            contract = self._confirmed(
                self.add_schedule(self.create_contract(), "2027-01-10")
            )
        down_payment = self._line(contract, "down_payment")
        self.assertEqual(down_payment.date_due, date(2027, 1, 10))
        self.assertEqual(down_payment.date_effective_due, date(2027, 1, 30))
        self._night("2027-02-06")
        self.assertEqual(down_payment.days_past_due, 7)
        self.assertFalse(down_payment.is_overdue)
        self.assertEqual(down_payment.late_fee_accrued, 0)
        self._night("2027-02-08")
        self.assertTrue(down_payment.is_overdue)
        self.assertEqual(down_payment.late_fee_accrued, 9 * 858_000 / 3000)
