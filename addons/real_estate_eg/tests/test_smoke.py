from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSmoke(TransactionCase):
    """Proves the test runner finds and runs this module's tests (S01.2)."""

    def test_module_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "real_estate_eg")])
        self.assertEqual(module.state, "installed")
