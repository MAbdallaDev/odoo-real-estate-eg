from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestSchedule(RealEstateCommon):
    def test_br_19_schedule_lines_locked(self):
        """BR-19 / BR-18: lines change only on a draft, for everyone; the total
        leaves the maintenance deposit out."""
        contract = self.create_contract()
        Line = self.env["real.estate.installment"].with_user(self.agent_a)
        lines = Line.create(
            [
                {
                    "contract_id": contract.id,
                    "line_type": "down_payment",
                    "amount": 8_580_000,
                    "date_due": "2027-01-10",
                },
                {
                    "contract_id": contract.id,
                    "line_type": "maintenance",
                    "amount": 686_400,
                },
            ]
        )
        self.assertEqual(contract.schedule_total, 8_580_000)
        self.assertEqual(lines[0].name, "Down Payment")

        contract.with_user(self.manager).action_confirm()
        for user in (self.agent_a, self.manager):
            with self.subTest(user=user.login):
                with self.assertRaises(UserError):
                    lines[0].with_user(user).write({"amount": 1})
                with self.assertRaises(UserError):
                    lines[1].with_user(user).unlink()
                with self.assertRaises(UserError):
                    Line.with_user(user).create(
                        {
                            "contract_id": contract.id,
                            "line_type": "installment",
                            "number": 1,
                            "amount": 1,
                        }
                    )
        # The superuser passes (Story 04's nightly job).
        lines[1].sudo().write({"date_due": "2027-06-30"})
