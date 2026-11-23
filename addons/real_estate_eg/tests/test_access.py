from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestReadOnlyRoles(RealEstateCommon):
    """US-06 / BR-35: collections officers and accountants read every contract
    and edit none. Enforced here by access rights (ir.model.access.csv);
    record rules come in Story 06."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contract = cls.env["real.estate.contract"].create(
            {
                "partner_id": cls.customer_eg.id,
                "unit_id": cls.unit_3br.id,
                "user_id": cls.agent_a.id,
            }
        )
        cls.contract.with_user(cls.manager).action_confirm()
        # A draft too: there the Step 8 guard does not apply, so only the
        # access rights stop an edit.
        cls.draft = cls.env["real.estate.contract"].create(
            {
                "partner_id": cls.customer_eg.id,
                "unit_id": cls.unit_2br.id,
                "user_id": cls.agent_a.id,
            }
        )

    def _assert_reads_but_cannot_edit(self, user):
        contract = self.contract.with_user(user)
        # Reads: the contract, its price, and the projects and units.
        self.assertEqual(contract.price, 8_580_000)
        Contract = self.env["real.estate.contract"].with_user(user)
        self.assertIn(self.contract, Contract.search([]))
        self.unit_3br.with_user(user).read(["code", "list_price", "state"])

        # Edits nothing, draft or confirmed: no field (the price included), no
        # create or delete.
        draft = self.draft.with_user(user)
        new_unit = self.make_unit(f"HNC-T-{user.login}")
        edits = {
            "price": lambda: contract.write({"price": 1}),
            "contract date": lambda: contract.write({"date": "2026-01-01"}),
            "draft price": lambda: draft.write({"price": 1}),
            "draft customer": lambda: draft.write(
                {"partner_id": self.customer_foreign.id}
            ),
            "create": lambda: Contract.create(
                {"partner_id": self.customer_eg.id, "unit_id": new_unit.id}
            ),
            "delete draft": draft.unlink,
            "unit list price": lambda: self.unit_3br.with_user(user).write(
                {"list_price": 1}
            ),
            "project": lambda: self.project.with_user(user).write({"name": "X"}),
            "confirm/deliver/cancel": contract.action_deliver,
        }
        for edit, action in edits.items():
            with self.subTest(edit), self.assertRaises(AccessError):
                action()

    def test_ac_06_3_collections_reads_cannot_edit(self):
        """AC-06.3: a collections officer sees all contracts but cannot edit
        the price (plan and schedule arrive in Story 03, read-only the same way)."""
        self._assert_reads_but_cannot_edit(self.collections)
        # ...but can log a follow-up note in the chatter.
        self.contract.with_user(self.collections).message_post(
            body="Called the customer about the next installment.",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def test_ac_06_5_accountant_reads_cannot_edit(self):
        """AC-06.5: an accountant (Odoo's Invoicing group) sees all contracts but
        cannot edit them (schedules arrive in Story 03)."""
        self._assert_reads_but_cannot_edit(self.accountant)
