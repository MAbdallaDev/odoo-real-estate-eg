from datetime import date

from freezegun import freeze_time

from odoo.exceptions import AccessError
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

    def test_ac_05_4_idempotent(self):
        """T8. AC-05.4 / BR-29: the fee is overwritten from the payment
        history, never added to: twice the same night = once; a skipped night
        changes nothing; a payment entered late with an earlier date gives the
        fee it would have had if entered on time."""
        __, line = self._installment_1_invoiced()
        self._pay(line, 141_313, "2027-04-30")
        expected = (20 * 241_313 + 20 * 100_000) / 3000  # 10-29 Apr, 30 Apr-19 May
        self._night("2027-05-20")
        self.assertAlmostEqual(line.late_fee_accrued, expected, places=9)
        self._night("2027-05-20")
        self.assertAlmostEqual(line.late_fee_accrued, expected, places=9)
        # 21 May skipped; 22 May counts both days.
        self._night("2027-05-22")
        self.assertAlmostEqual(
            line.late_fee_accrued, (20 * 241_313 + 22 * 100_000) / 3000, places=9
        )
        # The rest was paid on 21 May but entered only on 25 May.
        self._pay(line, 100_000, "2027-05-21", entered="2027-05-25")
        self._night("2027-05-25")
        self.assertAlmostEqual(
            line.late_fee_accrued, (20 * 241_313 + 21 * 100_000) / 3000, places=9
        )
        self.assertTrue(line.late_fee_final)

    def test_ac_05_6_at_risk(self):
        """T9. AC-05.6 / BR-31: 60 days past due -> not at risk; 61 -> at risk,
        the contract stays confirmed; paying the line clears the flag."""
        contract, line = self._installment_1_invoiced()
        self._pay(self._line(contract, "down_payment"), 858_000, "2027-01-10")
        self._night("2027-06-09")
        self.assertEqual(line.days_past_due, 60)
        self.assertFalse(contract.at_risk)
        self._night("2027-06-10")
        self.assertEqual(line.days_past_due, 61)
        self.assertTrue(contract.at_risk)
        self.assertEqual(contract.state, "confirmed")
        self.assertTrue(contract.with_user(self.collections).at_risk)
        self._pay(line, 241_313, "2027-06-11")
        self.assertFalse(contract.at_risk)

    def _example_d_paid_25_may(self):
        """Down payment paid on time; installment 1 paid in full on 25 May;
        the nightly job has run that day: 3,619.695 accrued."""
        contract, line = self._installment_1_invoiced()
        self._pay(self._line(contract, "down_payment"), 858_000, "2027-01-10")
        self._pay(line, 241_313, "2027-05-25")
        self._night("2027-05-25")
        return contract, line

    def test_ac_05_7_bill_once(self):
        """T10. AC-05.7 / BR-30 / BR-35: a collections officer bills all
        unbilled fees in one invoice rounded once: 3,619.695 -> 3,620, to the
        Late Fees account, no tax. Billing again creates nothing. A manager
        may bill; an agent or an accountant may not."""
        contract, line = self._example_d_paid_25_may()
        self.assertEqual(contract.late_fee_unbilled, 3619.70)
        for user in (self.agent_a, self.accountant):
            with self.assertRaises(AccessError):
                contract.with_user(user).action_bill_late_fees()

        with freeze_time("2027-05-26"):
            contract.with_user(self.collections).action_bill_late_fees()
        invoices = contract.sudo().late_fee_invoice_ids
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.state, "posted")
        self.assertEqual(invoices.amount_total, 3620)
        self.assertEqual(invoices.amount_tax, 0)
        self.assertEqual(invoices.invoice_line_ids.account_id, self.late_fee_account)
        self.assertEqual(line.late_fee_billed, 3619.695)
        self.assertEqual(line.late_fee_unbilled, 0)
        self.assertEqual(contract.late_fee_unbilled, 0)
        self.assertIn("3,620", contract.message_ids[:1].body)

        with freeze_time("2027-05-26"):
            contract.with_user(self.collections).action_bill_late_fees()
            contract.with_user(self.manager).action_bill_late_fees()
        self.assertEqual(len(contract.sudo().late_fee_invoice_ids), 1)

    def test_ac_05_9_fee_invoice_never_accrues(self):
        """T11. AC-05.9: the late-fee invoice is not a schedule line: unpaid
        for 44 days, then paid late, it accrues nothing and never makes the
        contract at risk."""
        contract, line = self._example_d_paid_25_may()
        with freeze_time("2027-05-26"):
            contract.with_user(self.manager).action_bill_late_fees()
        fee_invoice = contract.sudo().late_fee_invoice_ids
        self._night("2027-07-09")
        with freeze_time("2027-07-09"):
            self._register_payment(fee_invoice, payment_date="2027-07-09")
        self._night("2027-07-09")
        self.assertEqual(line.late_fee_accrued, 3619.695)
        self.assertEqual(contract.late_fee_unbilled, 0)
        self.assertFalse(contract.at_risk)
