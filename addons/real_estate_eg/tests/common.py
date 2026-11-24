from odoo.tests import Form, new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

# Fixtures from docs/business-requirements.md §6.1, §6.2, §6.3 and §6.6 (example A).
GROUP = "real_estate_eg.group_real_estate_"


class RealEstateCommon(AccountTestInvoicingCommon):
    """Shared fixtures. Records are set up here; every action under test runs
    with_user() as one of the users below, never as admin.

    Story 04: the base is Odoo's accounting test class. It gives a test company
    with a chart of accounts and a bank journal whose inbound payments post to
    Outstanding Receipts, so registered payments lower the invoice's amount due.
    It also switches cls.env to its own user and company in super().setUpClass(),
    so every fixture below is created after that call, in the test company."""

    @classmethod
    def get_default_groups(cls):
        # The setup user also needs to create projects, units and plans.
        return super().get_default_groups() | cls.env.ref(GROUP + "manager")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # BR-43 / BR-23: the two liability accounts schedule-line invoices post to.
        Account = cls.env["account.account"]
        cls.advance_account = Account.create(
            {
                "code": "RE2101",
                "name": "Customer Advances",
                "account_type": "liability_current",
            }
        )
        cls.maintenance_account = Account.create(
            {
                "code": "RE2102",
                "name": "Maintenance Deposits",
                "account_type": "liability_current",
            }
        )
        cls.env.company.write(
            {
                "re_advance_account_id": cls.advance_account.id,
                "re_maintenance_account_id": cls.maintenance_account.id,
            }
        )

        new_user = new_test_user
        cls.agent_a = new_user(cls.env, login="re_agent_a", groups=GROUP + "agent")
        cls.agent_b = new_user(cls.env, login="re_agent_b", groups=GROUP + "agent")
        cls.manager = new_user(cls.env, login="re_manager", groups=GROUP + "manager")
        cls.collections = new_user(
            cls.env, login="re_collections", groups=GROUP + "collections"
        )
        cls.accountant = new_user(
            cls.env, login="re_accountant", groups="account.group_account_invoice"
        )

        cls.project = cls.env["real.estate.project"].create(
            {"name": "Horizon New Cairo", "code": "HNC", "location": "New Cairo"}
        )
        Unit = cls.env["real.estate.unit"]
        cls.unit_3br = Unit.create(
            {
                "code": "HNC-B07-0302",
                "project_id": cls.project.id,
                "unit_type": "apartment",
                "bedrooms": 3,
                "area": 165,
                "floor": 3,
                "list_price": 8_580_000,
            }
        )
        cls.unit_2br = Unit.create(
            {
                "code": "HNC-B07-0301",
                "project_id": cls.project.id,
                "unit_type": "apartment",
                "bedrooms": 2,
                "area": 125,
                "floor": 3,
                "list_price": 6_500_000,
            }
        )

        Partner = cls.env["res.partner"]
        cls.customer_eg = Partner.create(
            {
                "name": "Fictional Buyer EG",
                "nationality": "egyptian",
                "national_id": "29901158800017",
            }
        )
        cls.customer_eg_no_id = Partner.create(
            {"name": "Fictional Buyer EG No ID", "nationality": "egyptian"}
        )
        cls.customer_foreign = Partner.create(
            {
                "name": "Fictional Buyer Foreign",
                "nationality": "foreign",
                "passport_number": "X1234567",
            }
        )
        cls.customer_company = Partner.create(
            {"name": "Fictional Buyer Company", "is_company": True}
        )

        # §6.3 payment plans used by the schedule tests.
        Plan = cls.env["real.estate.plan.template"]
        cls.plan_std = Plan.create(
            {
                "name": "Standard 8 years",
                "code": "NH-STD-8Q",
                "down_payment_percent": 10,
                "installment_count": 32,
                "frequency": "quarterly",
                "first_installment_months": 3,
                "maintenance_percent": 8,
                "maintenance_due": "delivery",
            }
        )
        cls.plan_biz = Plan.create(
            {
                "name": "Business 5 years",
                "code": "NH-BIZ-5M",
                "down_payment_percent": 20,
                "installment_count": 60,
                "frequency": "monthly",
                "first_installment_months": 1,
                "maintenance_percent": 10,
                "maintenance_due": "signing",
            }
        )
        cls.plan_cash = Plan.create(
            {
                "name": "Cash",
                "code": "NH-CASH",
                "down_payment_percent": 100,
                "installment_count": 0,
                "maintenance_percent": 8,
                "maintenance_due": "delivery",
            }
        )

    def generate_schedule(self, contract, plan, user=None):
        """Generate through the dialog, as `user` (default: agent A) does in the UI."""
        user = user or self.agent_a
        action = contract.with_user(user).action_generate_schedule()
        Wizard = self.env[action["res_model"]].with_user(user)
        with Form(Wizard.with_context(**action["context"])) as wizard:
            wizard.plan_id = plan
        wizard.record.action_generate()

    @classmethod
    def add_schedule(cls, contract, day="2026-01-10"):
        """BR-10: confirmation needs a schedule. Sets a past contract date if
        empty, then generates NH-STD-8Q as the contract's own agent."""
        agent_contract = contract.with_user(contract.user_id)
        if not contract.date:
            agent_contract.date = day
        agent_contract._generate_schedule(cls.plan_std)
        return contract

    def make_unit(self, code):
        """A free unit like the 2-bedroom one, for tests needing several."""
        return self.unit_2br.copy({"code": code})

    def create_contract(self, user=None, unit=None, partner=None):
        """A draft contract created by `user` (default: agent A)."""
        user = user or self.agent_a
        return (
            self.env["real.estate.contract"]
            .with_user(user)
            .create(
                {
                    "partner_id": (partner or self.customer_eg).id,
                    "unit_id": (unit or self.unit_3br).id,
                    "user_id": user.id,
                }
            )
        )
