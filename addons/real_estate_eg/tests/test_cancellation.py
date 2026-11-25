from freezegun import freeze_time

from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestCancellation(RealEstateCommon):
    def _example_e(self):
        """Example E on 10 Apr 2028: Example A with the down payment and
        installments 1-4 paid (1,823,252); installment 5 (due today) invoiced
        and unpaid."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
        with freeze_time("2028-04-10"):
            self.env["real.estate.contract"].sudo()._cron_nightly()
            paid = contract.installment_ids.filtered(
                lambda x: x.line_type != "maintenance" and x.number <= 4
            )
            for line in paid:
                self._register_payment(line.sudo().invoice_id)
        return contract

    def _cancel(self, contract):
        with freeze_time("2028-04-10"):
            contract.with_user(self.manager)._cancel_with_reason("Customer request")

    def test_ac_09_3_retention_example_e(self):
        """AC-09.3 / BR-33: retention 15% of 1,823,252 = 273,488; refundable
        1,549,764; computed from payments, unchanged by the credit notes."""
        contract = self._example_e()
        self.assertEqual(contract.amount_paid, 1_823_252)

        self._cancel(contract)
        self.assertEqual(contract.state, "cancelled")
        self.assertEqual(contract.retention_amount, 273_488)
        self.assertEqual(contract.refundable_amount, 1_549_764)
        # A credit note is not a payment: installment 5 shows nothing paid.
        installment_5 = contract.installment_ids.filtered(lambda x: x.number == 5)
        self.assertEqual(installment_5.amount_paid, 0)
        self.assertEqual(contract.amount_paid, 1_823_252)
