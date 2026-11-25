from freezegun import freeze_time

from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestDeliveryClosing(RealEstateCommon):
    def _cash_contract(self, plan=None):
        """A cash sale (100% down payment) of the 3-bedroom unit, confirmed on
        10 Jan 2027: the down payment is invoiced at once."""
        with freeze_time("2027-01-10"):
            contract = self.create_contract()
            contract.date = "2027-01-10"
            contract._generate_schedule(plan or self.plan_cash)
            return self._confirmed(contract)

    def _pay(self, contract, line_type):
        self._register_payment(self._line(contract, line_type).sudo().invoice_id)

    def _run_job(self, day):
        with freeze_time(day):
            self.env["real.estate.contract"].sudo()._cron_nightly()

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

    def test_ac_12_1_close_when_paid(self):
        """US-12 / AC-12.1 / BR-12: a delivered contract closes on the next nightly run
        once its last unpaid line is paid, not before."""
        contract = self._cash_contract()
        with freeze_time("2027-02-01"):
            contract.with_user(self.manager).action_deliver()
        self._pay(contract, "down_payment")
        self._run_job("2027-02-02")
        self.assertEqual(contract.state, "delivered", "the deposit is not paid")

        self._pay(contract, "maintenance")
        self._run_job("2027-02-03")
        self.assertEqual(contract.state, "closed")
        self.assertEqual(contract.unit_id.state, "delivered")

    def test_ac_12_2_confirmed_paid_stays_open(self):
        """AC-12.2: a confirmed contract that is fully paid stays confirmed.
        A cash plan with the deposit at signing: both lines invoiced and paid
        before delivery."""
        plan = self.plan_cash.copy(
            {"code": "NH-CASH-SIGN", "maintenance_due": "signing"}
        )
        contract = self._cash_contract(plan)
        self._pay(contract, "down_payment")
        self._pay(contract, "maintenance")
        self.assertEqual(set(contract.installment_ids.mapped("state")), {"paid"})

        self._run_job("2027-02-01")
        self.assertEqual(contract.state, "confirmed")

    def test_br_12_close_waits_for_late_fees(self):
        """T12. BR-12: a delivered contract whose lines are all paid stays
        delivered while a late fee is unbilled, or billed and unpaid; it closes
        once the late-fee invoice is paid."""
        contract = self._cash_contract()
        with freeze_time("2027-02-01"):
            contract.with_user(self.manager).action_deliver()
            self._pay(contract, "maintenance")
        # The down payment (due 10 Jan) is paid 50 days late.
        down_payment = self._line(contract, "down_payment").sudo().invoice_id
        with freeze_time("2027-03-01"):
            self._register_payment(down_payment, payment_date="2027-03-01")
        self._run_job("2027-03-02")
        self.assertEqual(set(contract.installment_ids.mapped("state")), {"paid"})
        self.assertEqual(contract.late_fee_unbilled, 143_000)  # 50 x 8,580,000 / 3000
        self.assertEqual(contract.state, "delivered", "a late fee is unbilled")

        with freeze_time("2027-03-02"):
            contract.with_user(self.collections).action_bill_late_fees()
        self._run_job("2027-03-03")
        self.assertEqual(contract.state, "delivered", "the late fee is unpaid")

        with freeze_time("2027-03-03"):
            self._register_payment(contract.sudo().late_fee_invoice_ids)
        self._run_job("2027-03-04")
        self.assertEqual(contract.state, "closed")
