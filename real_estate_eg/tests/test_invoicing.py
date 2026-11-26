from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestInvoicing(RealEstateCommon):
    def test_settings_defaults(self):
        """BR-33, BR-22, BR-44: retention 15%, no lead days, products without taxes."""
        company = self.env.company
        self.assertEqual(company.re_retention_percent, 15)
        self.assertEqual(company.re_invoice_lead_days, 0)
        for xmlid in (
            "product_down_payment",
            "product_installment",
            "product_maintenance_deposit",
        ):
            product = self.env.ref("real_estate_eg." + xmlid)
            self.assertFalse(product.taxes_id, xmlid + " must carry no customer tax")
        # The settings page shows the same values for the current company.
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.re_advance_account_id, self.advance_account)
        self.assertEqual(settings.re_maintenance_account_id, self.maintenance_account)
        self.assertEqual(settings.re_retention_percent, 15)

    # ------------------------------------------------------------------
    # Step 2: one invoice per line. Confirmation does not invoice yet
    # (Step 3), so these tests call _create_invoices() directly.
    # ------------------------------------------------------------------

    def _invoice(self, line):
        """Invoice one line as the sales manager, who has no accounting rights."""
        line.with_user(self.manager)._create_invoices(fields.Date.today())
        return line.sudo().invoice_id

    @freeze_time("2027-01-10")
    def test_ac_03_7_advances_account(self):
        """AC-03.7 / BR-43: the down payment posts to customer advances, not revenue.
        Example A: receivable debit 858,000, advances credit 858,000."""
        contract = self._example_a()
        line = self._line(contract, "down_payment")
        invoice = self._invoice(line)

        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.partner_id, self.customer_eg)
        self.assertEqual(invoice.amount_total, 858_000)
        self.assertEqual(invoice.invoice_origin, contract.name)
        receivable = invoice.line_ids.filtered(
            lambda x: x.account_id.account_type == "asset_receivable"
        )
        product_line = invoice.invoice_line_ids
        self.assertEqual(receivable.debit, 858_000)
        self.assertEqual(product_line.account_id, self.advance_account)
        self.assertEqual(product_line.credit, 858_000)
        self.assertFalse(
            invoice.line_ids.filtered(lambda x: x.account_id.account_type == "income"),
            "no revenue in v1",
        )
        # BR-26: invoiced on its due date, so both dates are 10 Jan 2027.
        self.assertEqual(str(line.invoice_date), "2027-01-10")
        self.assertEqual(str(line.date_effective_due), "2027-01-10")
        # BR-25: a second call does not invoice the line again.
        line.with_user(self.manager)._create_invoices(fields.Date.today())
        self.assertEqual(line.sudo().invoice_id, invoice)

    @freeze_time("2027-01-31")
    def test_ac_03_3_maintenance_liability(self):
        """AC-03.3 / BR-23: Example C's deposit due at signing posts to the
        maintenance deposits liability account."""
        contract = self._confirmed(self._example_c())
        line = self._line(contract, "maintenance")
        invoice = self._invoice(line)

        self.assertEqual(invoice.amount_total, 366_000)
        self.assertEqual(invoice.invoice_line_ids.account_id, self.maintenance_account)
        self.assertEqual(
            invoice.invoice_line_ids.product_id,
            self.env.ref("real_estate_eg.product_maintenance_deposit"),
        )

    @freeze_time("2027-01-10")
    def test_ac_03_6_no_tax(self):
        """AC-03.6 / BR-44: no tax even when the company, the product and the
        account all carry a default sales tax."""
        tax = self.company_data["default_tax_sale"]
        self.assertTrue(tax, "the test chart has a default sales tax")
        self.env.company.account_sale_tax_id = tax
        self.env.ref("real_estate_eg.product_down_payment").taxes_id = tax
        self.advance_account.tax_ids = tax

        contract = self._example_a()
        line = self._line(contract, "down_payment")
        invoice = self._invoice(line)

        self.assertEqual(invoice.amount_tax, 0)
        self.assertEqual(invoice.amount_total, 858_000)
        self.assertFalse(invoice.invoice_line_ids.tax_ids)
        self.assertFalse(invoice.line_ids.filtered("tax_line_id"))

    def test_invoice_needs_confirmed_contract_and_account(self):
        """BR-22: a draft line is never invoiced; a missing account is named."""
        contract = self.add_schedule(self.create_contract())
        with self.assertRaisesRegex(UserError, "confirmed contract"):
            contract.installment_ids[:1]._create_invoices(fields.Date.today())

        # The deposit due at delivery is not invoiced at confirmation (no date).
        self._confirmed(contract)
        deposit = self._line(contract, "maintenance")
        self.env.company.re_maintenance_account_id = False
        with self.assertRaisesRegex(UserError, "Maintenance Deposits"):
            deposit._create_invoices(fields.Date.today())
        self.assertFalse(deposit.sudo().invoice_id)

    # ------------------------------------------------------------------
    # Step 3: confirmation invoices every line already due.
    # ------------------------------------------------------------------

    def test_ac_03_1_invoice_at_confirmation(self):
        """US-03 / AC-03.1 / AC-10.3 / BR-21: confirming invoices the lines already due,
        done by a sales manager who has no accounting rights."""
        self.assertFalse(self.manager.has_group("account.group_account_invoice"))

        # Example A confirmed on 10 Jan 2027: only the down payment is due;
        # the deposit due at delivery has no date yet.
        with freeze_time("2027-01-10"):
            contract_a = self._example_a()
        invoiced = self._invoiced(contract_a)
        self.assertEqual(invoiced.mapped("line_type"), ["down_payment"])
        self.assertEqual(invoiced.invoice_id.amount_total, 858_000)

        # Example C confirmed on 31 Jan 2027: down payment and deposit at signing.
        with freeze_time("2027-01-31"):
            contract_c = self._confirmed(self._example_c())
        invoiced = self._invoiced(contract_c)
        self.assertEqual(invoiced.mapped("line_type"), ["down_payment", "maintenance"])
        self.assertEqual(invoiced.invoice_id.mapped("amount_total"), [732_000, 366_000])

        # A contract dated a year back, confirmed on 10 Jan 2028: the down
        # payment and installments 1-4 are already due. BR-26: their invoices
        # fall due on the confirmation day, so nothing is late before it.
        with freeze_time("2028-01-10"):
            unit = self.make_unit("HNC-B07-0303")
            late = self.add_schedule(self.create_contract(unit=unit), "2027-01-10")
            self._confirmed(late)
        invoiced = self._invoiced(late)
        self.assertEqual(invoiced.mapped("number"), [0, 1, 2, 3, 4])
        for line in invoiced:
            self.assertEqual(str(line.invoice_id.invoice_date_due), "2028-01-10")
            self.assertEqual(str(line.date_effective_due), "2028-01-10")

    def test_confirmation_needs_accounts(self):
        """BR-43 / BR-23: no confirmation, and so no invoice, without the accounts."""
        self.env.company.re_maintenance_account_id = False
        contract = self.add_schedule(self.create_contract())
        with self.assertRaisesRegex(UserError, "Settings > Real Estate"):
            contract.with_user(self.manager).action_confirm()
        self.assertEqual(contract.state, "draft")

    # ------------------------------------------------------------------
    # Step 5: the nightly job invoices lines as they fall due.
    # ------------------------------------------------------------------

    def _run_job(self, day):
        """Run the nightly job as the cron does (superuser) on `day`."""
        with freeze_time(day):
            self.env["real.estate.contract"].sudo()._cron_nightly()

    def _invoice_count(self, contract):
        """Posted customer invoices made for the contract, counted in accounting
        (a duplicate would replace the line's link, so lines cannot tell)."""
        return self.env["account.move"].search_count(
            [("invoice_origin", "=", contract.name), ("move_type", "=", "out_invoice")]
        )

    def test_ac_03_2_job_invoices_once(self):
        """AC-03.2 / BR-22 / BR-25: the job posts one invoice for an installment
        due today and none on a second run; draft contracts are never
        invoiced; lead days invoice early but keep the due date."""
        with freeze_time("2027-01-10"):
            contract = self._example_a()
            unit = self.make_unit("HNC-B07-0303")
            draft = self.add_schedule(self.create_contract(unit=unit), "2027-01-10")
        installment_1 = contract.installment_ids.filtered(lambda x: x.number == 1)
        self.assertEqual(installment_1.state, "scheduled")

        self._run_job("2027-04-10")
        invoice = installment_1.sudo().invoice_id
        self.assertEqual(invoice.amount_total, 241_313)
        self.assertEqual(str(invoice.invoice_date), "2027-04-10")
        self.assertEqual(installment_1.state, "invoiced")
        self.assertEqual(self._invoice_count(contract), 2, "down payment + inst. 1")

        self._run_job("2027-04-10")
        self.assertEqual(self._invoice_count(contract), 2, "no second invoice")
        self.assertFalse(self._invoiced(draft), "a draft is never invoiced")

        # BR-22: 5 lead days invoice installment 2 (due 10 Jul) on 5 Jul; its
        # due date stays 10 Jul (BR-26), so it is not late before then.
        self.env.company.re_invoice_lead_days = 5
        installment_2 = contract.installment_ids.filtered(lambda x: x.number == 2)
        self._run_job("2027-07-04")
        self.assertFalse(installment_2.sudo().invoice_id, "6 days early: not yet")
        self._run_job("2027-07-05")
        invoice = installment_2.sudo().invoice_id
        self.assertEqual(str(invoice.invoice_date), "2027-07-05")
        self.assertEqual(str(invoice.invoice_date_due), "2027-07-10")
        self.assertEqual(str(installment_2.date_effective_due), "2027-07-10")
