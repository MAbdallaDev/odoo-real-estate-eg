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

    # ------------------------------------------------------------------
    # BR-35: who sees which contracts (Step 2; the agent rule is Step 3)
    # ------------------------------------------------------------------

    def test_ac_06_2_manager_sees_every_agent(self):
        """AC-06.2: a manager sees the contracts of every agent, with their
        schedule lines, and can edit every draft. The manager group implies
        the agent group, so this also guards against the agent rule hiding
        other agents' contracts from managers."""
        contract_b = self.add_schedule(
            self.create_contract(user=self.agent_b, unit=self.unit_2br)
        )
        contracts = self.contract_a | contract_b
        Contract = self.env["real.estate.contract"].with_user(self.manager)
        self.assertEqual(Contract.search([("id", "in", contracts.ids)]), contracts)
        Line = self.env["real.estate.installment"].with_user(self.manager)
        lines = contracts.installment_ids
        self.assertEqual(Line.search([("contract_id", "in", contracts.ids)]), lines)

        for contract in contracts:
            with self.subTest(agent=contract.user_id.login):
                contract.with_user(self.manager).partner_id = self.customer_foreign
                self.assertEqual(contract.partner_id, self.customer_foreign)

    def test_ac_06_1_agent_sees_own_only(self):
        """AC-06.1 / BR-35: agent B does not see agent A's contract or its
        schedule lines in a list, and opening them directly is refused.
        Agent A still sees both. (Written by Claude at the maintainer's
        request.)"""
        lines_a = self.contract_a.installment_ids
        self.assertTrue(lines_a)
        Contract = self.env["real.estate.contract"]
        Line = self.env["real.estate.installment"]

        # Agent B: not in the lists...
        self.assertNotIn(self.contract_a, Contract.with_user(self.agent_b).search([]))
        self.assertFalse(
            Line.with_user(self.agent_b).search([("id", "in", lines_a.ids)])
        )
        # ...and opening them directly gives an access error.
        with self.assertRaises(AccessError):
            self.contract_a.with_user(self.agent_b).read(["name"])
        with self.assertRaises(AccessError):
            lines_a[0].with_user(self.agent_b).read(["amount"])

        # Agent A: sees the contract and every line.
        self.assertIn(self.contract_a, Contract.with_user(self.agent_a).search([]))
        self.assertEqual(
            Line.with_user(self.agent_a).search(
                [("contract_id", "=", self.contract_a.id)]
            ),
            lines_a,
        )

    def test_agent_and_accountant_reads_all_writes_own(self):
        """BR-35: the collections and accounting "see all" rules are read
        only. A user who is both an agent and an accountant reads every
        contract but still edits only their own drafts."""
        agent_accountant = new_test_user(
            self.env,
            login="re_agent_accountant",
            groups=GROUP + "agent,account.group_account_invoice",
        )
        own = self.create_contract(user=agent_accountant, unit=self.unit_2br)
        other = self.contract_a.with_user(agent_accountant)
        self.assertEqual(other.name, self.contract_a.name)  # reads it
        with self.assertRaises(AccessError):
            other.partner_id = self.customer_foreign
        own.with_user(agent_accountant).partner_id = self.customer_foreign
        self.assertEqual(own.partner_id, self.customer_foreign)
