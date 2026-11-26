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

    def test_ac_09_4_credit_notes(self):
        """AC-09.4 / BR-34: an unpaid invoice is credited in full, a partly paid
        one for its remainder and matched; future lines are cancelled; every
        line shows cancelled; the unit is available."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
        with freeze_time("2027-04-10"):
            self.env["real.estate.contract"].sudo()._cron_nightly()
        down_payment = self._line(contract, "down_payment").sudo().invoice_id
        installment_1 = contract.installment_ids.filtered(lambda x: x.number == 1)
        invoice_1 = installment_1.sudo().invoice_id
        self._register_payment(invoice_1, amount=141_313)

        with freeze_time("2027-04-30"):
            contract.with_user(self.manager)._cancel_with_reason("Customer request")

        for invoice, credited in ((down_payment, 858_000), (invoice_1, 100_000)):
            refund = invoice.reversal_move_ids
            self.assertEqual(refund.move_type, "out_refund")
            self.assertEqual(refund.state, "posted")
            self.assertEqual(refund.amount_total, credited)
            self.assertEqual(refund.amount_tax, 0)
            self.assertEqual(refund.invoice_line_ids.account_id, self.advance_account)
            self.assertEqual(invoice.amount_residual, 0, "matched with the invoice")
            self.assertEqual(refund.amount_residual, 0)
        # The money really paid stays paid; the credit note is not a payment.
        self.assertEqual(installment_1.amount_paid, 141_313)
        self.assertEqual(contract.amount_outstanding, 0)

        self.assertEqual(set(contract.installment_ids.mapped("state")), {"cancelled"})
        self.assertEqual(len(self._invoiced(contract)), 2, "future lines: none")
        self.assertEqual(contract.unit_id.state, "available")

    def test_br_34_credit_late_fee_invoice(self):
        """T13. BR-34 / BR-33: on cancellation an unpaid late-fee invoice is
        credited in full and matched; a paid one is not refunded; retention
        counts only the down payment and installments."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
            self._register_payment(
                self._line(contract, "down_payment").sudo().invoice_id
            )
        Contract = self.env["real.estate.contract"].sudo()
        installments = contract.installment_ids.filtered(lambda x: x.number in (1, 2))
        # Each installment is invoiced on its due date by the nightly job.
        for day in ("2027-04-10", "2027-07-10"):
            with freeze_time(day):
                Contract._cron_nightly()
        # Installment 1 (due 10 Apr) paid 25 May: 3,620 billed and paid.
        with freeze_time("2027-05-25"):
            Contract._cron_nightly()
            self._register_payment(installments[0].sudo().invoice_id)
            Contract._cron_nightly()
            contract.with_user(self.collections).action_bill_late_fees()
            paid_fee = contract.sudo().late_fee_invoice_ids
            self._register_payment(paid_fee)
        # Installment 2 (due 10 Jul) unpaid on 25 Jul: its fee billed, unpaid.
        with freeze_time("2027-07-25"):
            Contract._cron_nightly()
            contract.with_user(self.collections).action_bill_late_fees()
        unpaid_fee = contract.sudo().late_fee_invoice_ids - paid_fee
        self.assertEqual(
            unpaid_fee.amount_total, 1207
        )  # 15 x 241,313 / 3000 = 1,206.565

        with freeze_time("2027-07-26"):
            contract.with_user(self.manager)._cancel_with_reason("Customer request")
        self.assertEqual(unpaid_fee.amount_residual, 0)
        self.assertEqual(unpaid_fee.payment_state, "reversed")
        refund = unpaid_fee.reversal_move_ids
        self.assertEqual(refund.amount_total, 1207)
        self.assertEqual(refund.invoice_line_ids.account_id, self.late_fee_account)
        self.assertEqual(paid_fee.payment_state, "paid")
        self.assertFalse(paid_fee.reversal_move_ids)
        # 15% of 858,000 + 241,313 = 1,099,313 -> 164,897 (half up).
        self.assertEqual(contract.retention_amount, 164_897)
        self.assertEqual(contract.refundable_amount, 934_416)
