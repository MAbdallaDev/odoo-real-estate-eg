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
