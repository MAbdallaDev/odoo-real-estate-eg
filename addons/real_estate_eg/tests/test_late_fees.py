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
