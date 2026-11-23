from odoo.tests import TransactionCase, new_test_user

# Fixtures from docs/business-requirements.md §6.1, §6.2 and §6.6 (example A).
GROUP = "real_estate_eg.group_real_estate_"


class RealEstateCommon(TransactionCase):
    """Shared fixtures. Records are set up here; every action under test runs
    with_user() as one of the users below, never as admin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
