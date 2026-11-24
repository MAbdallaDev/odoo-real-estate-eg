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
