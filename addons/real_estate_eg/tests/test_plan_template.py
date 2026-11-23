from psycopg2.errors import CheckViolation, UniqueViolation

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestPlanTemplate(RealEstateCommon):
    def _create_plan(self, user=None, **values):
        """Plan NH-STD-8Q from §6.3, created by `user` (default: manager),
        with `values` overriding its fields."""
        vals = {
            "name": "Standard 8 years",
            "code": "NH-STD-8Q",
            "down_payment_percent": 10,
            "installment_count": 32,
            "frequency": "quarterly",
            "first_installment_months": 3,
            "maintenance_percent": 8,
            "maintenance_due": "delivery",
        }
        vals.update(values)
        Plan = self.env["real.estate.plan.template"]
        return Plan.with_user(user or self.manager).create(vals)

    def test_br_14_plan_template_limits(self):
        """BR-14: a manager defines plans within sensible limits; others read them."""
        plan = self._create_plan()
        self.assertEqual(plan.installment_count, 32)
        for user in (self.agent_a, self.collections, self.accountant):
            with self.subTest(user=user.login):
                self.assertEqual(plan.with_user(user).code, "NH-STD-8Q")
                with self.assertRaises(AccessError):
                    self._create_plan(user=user, code="NH-OTHER")

        refused = {
            "down payment above 100%": {"down_payment_percent": 101},
            "negative down payment": {"down_payment_percent": -1},
            "maintenance above 100%": {"maintenance_percent": 150},
            "negative installments": {"installment_count": -1},
            "negative months": {"first_installment_months": -3},
        }
        for case, values in refused.items():
            with self.subTest(case), mute_logger("odoo.sql_db"):
                with self.assertRaises(CheckViolation):
                    self._create_plan(code="NH-BAD", **values)

        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self._create_plan(name="Same code")

    def test_br_20_cash_plan(self):
        """BR-20: 0 installments and 100% down is a valid cash plan; other
        mixes that cannot add up to the price are refused."""
        cash = self._create_plan(
            name="Cash",
            code="NH-CASH",
            down_payment_percent=100,
            installment_count=0,
            frequency=False,
            first_installment_months=0,
        )
        self.assertEqual(cash.installment_count, 0)

        refused = {
            "no installments, 90% down": {
                "installment_count": 0,
                "down_payment_percent": 90,
            },
            "installments, 100% down": {"down_payment_percent": 100},
            "installments, no frequency": {"frequency": False},
        }
        for case, values in refused.items():
            with self.subTest(case), self.assertRaises(ValidationError):
                self._create_plan(code="NH-BAD", **values)
