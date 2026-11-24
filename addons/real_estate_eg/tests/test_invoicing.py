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

    def _confirmed(self, contract):
        contract.with_user(self.manager).action_confirm()
        return contract

    def _example_a(self):
        """Example A, confirmed on its contract date 10 Jan 2027."""
        return self._confirmed(self.add_schedule(self.create_contract(), "2027-01-10"))

    @staticmethod
    def _line(contract, line_type):
        return contract.installment_ids.filtered(lambda x: x.line_type == line_type)

    def _invoice(self, line):
        """Invoice one line as the sales manager, who has no accounting rights."""
        line.with_user(self.manager)._create_invoices(fields.Date.today())
        return line.sudo().invoice_id

    @freeze_time("2027-01-10")
    def test_ac_03_7_advances_account(self):
        """AC-03.7 / BR-43: the down payment posts to customer advances, not revenue.
        Example A: receivable debit 858,000, advances credit 858,000."""
        contract = self._confirmed(
            self.add_schedule(self.create_contract(), "2027-01-10")
        )
        line = contract.installment_ids.filtered(
            lambda x: x.line_type == "down_payment"
        )
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
        office = self.make_unit("CBP-A02-0105")
        office.list_price = 3_660_000
        contract = self.create_contract(unit=office)
        contract.date = "2027-01-31"
        contract._generate_schedule(self.plan_biz)
        self._confirmed(contract)
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

        contract = self._confirmed(
            self.add_schedule(self.create_contract(), "2027-01-10")
        )
        line = contract.installment_ids.filtered(
            lambda x: x.line_type == "down_payment"
        )
        invoice = self._invoice(line)

        self.assertEqual(invoice.amount_tax, 0)
        self.assertEqual(invoice.amount_total, 858_000)
        self.assertFalse(invoice.invoice_line_ids.tax_ids)
        self.assertFalse(invoice.line_ids.filtered("tax_line_id"))

    def test_invoice_needs_confirmed_contract_and_account(self):
        """BR-22: a draft line is never invoiced; a missing account is named."""
        contract = self.add_schedule(self.create_contract())
        line = contract.installment_ids[:1]
        with self.assertRaisesRegex(UserError, "confirmed contract"):
            line._create_invoices(fields.Date.today())

        self._confirmed(contract)
        self.env.company.re_advance_account_id = False
        with self.assertRaisesRegex(UserError, "Customer Advances"):
            line._create_invoices(fields.Date.today())
        self.assertFalse(line.sudo().invoice_id)
