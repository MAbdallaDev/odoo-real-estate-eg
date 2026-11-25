from freezegun import freeze_time

from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestDeliveryClosing(RealEstateCommon):
    def test_ac_11_2_deposit_due_on_delivery(self):
        """AC-11.2 / AC-11.3 / BR-18 / BR-23: on delivery the deposit due at
        delivery gets the delivery date and is invoiced to the maintenance
        deposits account; installments not yet due stay scheduled."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
        deposit = self._line(contract, "maintenance")
        self.assertFalse(deposit.date_due, "no date before delivery")

        with freeze_time("2027-03-01"):
            contract.with_user(self.manager).action_deliver()
        self.assertEqual(contract.state, "delivered")
        self.assertEqual(str(deposit.date_due), "2027-03-01")
        invoice = deposit.sudo().invoice_id
        self.assertEqual(invoice.amount_total, 686_400)
        self.assertEqual(invoice.invoice_line_ids.account_id, self.maintenance_account)
        self.assertEqual(deposit.state, "invoiced")

        installment_1 = contract.installment_ids.filtered(lambda x: x.number == 1)
        self.assertEqual(str(installment_1.date_due), "2027-04-10")
        self.assertEqual(installment_1.state, "scheduled")
