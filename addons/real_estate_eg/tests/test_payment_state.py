from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestPaymentState(RealEstateCommon):
    """BR-24: a line's state and amounts are read from its invoice. Payments go
    through Odoo's register-payment wizard on the test bank journal, whose
    inbound payments post to Outstanding Receipts."""

    def _installment_1_invoiced(self):
        """Example A confirmed on 10 Jan 2027; installment 1 (241,313) invoiced
        on its due date, 10 Apr 2027."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
        with freeze_time("2027-04-10"):
            contract._invoice_due_lines(fields.Date.today())
        line = contract.installment_ids.filtered(lambda x: x.number == 1)
        return contract, line

    def test_ac_03_4_partial_then_paid(self):
        """AC-03.4: 141,313 of 241,313 paid → partly paid with 100,000 left;
        the rest paid → paid, also while accounting shows "In payment"."""
        contract, line = self._installment_1_invoiced()
        invoice = line.sudo().invoice_id
        self.assertEqual(invoice.amount_total, 241_313)
        self.assertEqual(line.state, "invoiced")

        with freeze_time("2027-04-30"):
            self._register_payment(invoice, amount=141_313)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertEqual(line.state, "partially_paid")
        self.assertEqual(line.amount_paid, 141_313)
        self.assertEqual(line.amount_residual, 100_000)

        # With the Accountant app an invoice is "In payment" until the bank
        # statement is matched. Odoo's own tests patch this hook the same way.
        def in_payment(move):
            return "in_payment"

        Move = self.env.registry["account.move"]
        with (
            patch.object(Move, "_get_invoice_in_payment_state", in_payment),
            freeze_time("2027-05-25"),
        ):
            self._register_payment(invoice, amount=100_000)
            self.assertEqual(invoice.payment_state, "in_payment")
            self.assertEqual(line.state, "paid")
        self.assertEqual(line.amount_paid, 241_313)
        self.assertEqual(line.amount_residual, 0)

    def test_ac_03_5_contract_totals(self):
        """AC-03.5: total paid and total outstanding from accounting, readable by
        the agent and collections, who have no rights on invoices. Lines not
        invoiced yet are not outstanding."""
        contract, line = self._installment_1_invoiced()
        down_payment = self._line(contract, "down_payment")
        with freeze_time("2027-04-30"):
            self._register_payment(down_payment.sudo().invoice_id)
            self._register_payment(line.sudo().invoice_id, amount=141_313)

        for user in (self.agent_a, self.collections):
            as_user = contract.with_user(user)
            self.assertEqual(as_user.amount_paid, 858_000 + 141_313)
            self.assertEqual(as_user.amount_outstanding, 100_000)
            states = as_user.installment_ids.mapped("state")
            self.assertEqual(states[:2], ["paid", "partially_paid"])
            self.assertEqual(set(states[2:]), {"scheduled"})
