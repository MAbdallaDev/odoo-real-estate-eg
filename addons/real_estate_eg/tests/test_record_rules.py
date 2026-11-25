from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import GROUP, RealEstateCommon


@tagged("post_install", "-at_install")
class TestRecordRules(RealEstateCommon):
    """US-06 / BR-35 / BR-36: record rules decide which rows each user sees.
    Every check runs as a real user (with_user), never as admin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Agent A's contract, with a schedule, in the test company (company 1).
        cls.contract_a = cls.add_schedule(
            cls.env["real.estate.contract"].create(
                {
                    "partner_id": cls.customer_eg.id,
                    "unit_id": cls.unit_3br.id,
                    "user_id": cls.agent_a.id,
                }
            )
        )

    # ------------------------------------------------------------------
    # BR-36: multi-company (Step 1)
    # ------------------------------------------------------------------

    def test_ac_06_4_other_company_hidden(self):
        """AC-06.4: a user allowed only in company 2 cannot see company 1's
        contracts or units (nor its projects, plans or schedule lines)."""
        company_2 = self.setup_other_company(name="Nile Heights West")["company"]
        env_2 = self.env(
            context=dict(self.env.context, allowed_company_ids=[company_2.id])
        )
        project_2 = env_2["real.estate.project"].create(
            {"name": "West Towers", "code": "WTW", "company_id": company_2.id}
        )
        unit_2 = env_2["real.estate.unit"].create(
            {
                "code": "WTW-A01-0101",
                "project_id": project_2.id,
                "unit_type": "apartment",
                "bedrooms": 2,
                "area": 120,
                "floor": 1,
                "list_price": 5_000_000,
            }
        )
        plan_2 = env_2["real.estate.plan.template"].create(
            {
                "name": "Cash West",
                "code": "WTW-CASH",
                "down_payment_percent": 100,
                "installment_count": 0,
                "company_id": company_2.id,
            }
        )
        manager_2 = new_test_user(
            self.env,
            login="re_manager_company_2",
            groups=GROUP + "manager",
            company_id=company_2.id,
            company_ids=[company_2.id],
        )
        contract_2 = (
            self.env["real.estate.contract"]
            .with_user(manager_2)
            .create({"partner_id": self.customer_eg.id, "unit_id": unit_2.id})
        )
        self.assertEqual(contract_2.company_id, company_2)

        # The company 2 user sees company 2's rows, and only those.
        expected = {
            "real.estate.project": project_2,
            "real.estate.unit": unit_2,
            "real.estate.plan.template": plan_2,
            "real.estate.contract": contract_2,
            "real.estate.installment": self.env["real.estate.installment"],
        }
        for model, records in expected.items():
            with self.subTest(model=model):
                found = self.env[model].with_user(manager_2).search([])
                self.assertEqual(found, records)

        # Opening a company 1 record directly gives an access error.
        company_1_records = {
            "contract": self.contract_a,
            "unit": self.unit_3br,
            "project": self.project,
            "plan": self.plan_std,
            "schedule line": self.contract_a.installment_ids[0],
        }
        for name, record in company_1_records.items():
            with self.subTest(record=name), self.assertRaises(AccessError):
                record.with_user(manager_2).read(["display_name"])

        # The other way round: a company 1 manager does not see company 2.
        Contract = self.env["real.estate.contract"].with_user(self.manager)
        self.assertNotIn(contract_2, Contract.search([]))
        self.assertIn(self.contract_a, Contract.search([]))
        with self.assertRaises(AccessError):
            unit_2.with_user(self.manager).read(["code"])
