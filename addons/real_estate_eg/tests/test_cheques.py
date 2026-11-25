from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestCheques(RealEstateCommon):
    """US-13 / BR-40 - BR-42: post-dated cheques. Every check runs as a real
    user (with_user), never as admin."""

    def setUp(self):
        super().setUp()
        # Example A (agent A), confirmed on 10 Jan 2027.
        with freeze_time("2027-01-10"):
            self.contract = self._example_a()
        self.line = self.contract.installment_ids.filtered(lambda x: x.number == 1)

    def _record(self, user, line=None, **values):
        """Record a cheque as `user` on `line` (default: installment 1)."""
        vals = {
            "name": "100001",
            "bank_name": "Fictional Bank of Egypt",
            "date": "2027-04-10",
            "amount": 214_500,
            "line_id": (line or self.line).id,
        }
        vals.update(values)
        return self.env["real.estate.cheque"].with_user(user).create(vals)

    # ------------------------------------------------------------------
    # AC-13.1: recorded on a confirmed or delivered contract, starts held
    # ------------------------------------------------------------------

    def test_ac_13_1_record_cheque(self):
        # Collections and the manager both record; "state" in the values is
        # ignored: a new cheque is always held.
        cheque = self._record(self.collections, state="cleared")
        self.assertEqual(cheque.state, "held")
        self.assertEqual(cheque.contract_id, self.contract)
        self.assertEqual(cheque.amount, 214_500)
        by_manager = self._record(self.manager, name="100002")
        self.assertEqual(by_manager.state, "held")
        self.assertEqual(self.line.cheque_ids, cheque | by_manager)

        # A delivered contract takes cheques too.
        with freeze_time("2027-06-01"):
            self.contract.with_user(self.manager).action_deliver()
        self.assertEqual(self.contract.state, "delivered")
        self.assertEqual(self._record(self.collections, name="100003").state, "held")

    def test_ac_13_1_refused_unless_confirmed(self):
        draft = self.add_schedule(self.create_contract(unit=self.unit_2br))
        draft_line = draft.installment_ids[:1]
        with self.assertRaises(UserError):
            self._record(self.collections, line=draft_line)

        draft.with_user(self.agent_a).action_cancel()
        self.assertEqual(draft.state, "cancelled")
        with self.assertRaises(UserError):
            self._record(self.manager, line=draft_line)

        # BR-40: an amount above 0, held by the database.
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self._record(self.collections, amount=0)

    # ------------------------------------------------------------------
    # BR-35: R (own) / W / W / R
    # ------------------------------------------------------------------

    def test_cheque_rights(self):
        cheque = self._record(self.collections)
        Cheque = self.env["real.estate.cheque"]

        # Agent A reads the cheques on their own contract; agent B sees none.
        self.assertEqual(Cheque.with_user(self.agent_a).search([]), cheque)
        self.assertEqual(cheque.with_user(self.agent_a).bank_name, cheque.bank_name)
        self.assertFalse(Cheque.with_user(self.agent_b).search([]))
        with self.assertRaises(AccessError):
            cheque.with_user(self.agent_b).read(["name"])

        # The accountant reads all; agents and the accountant change nothing.
        self.assertEqual(Cheque.with_user(self.accountant).search([]), cheque)
        for user in (self.agent_a, self.accountant):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self._record(user, name="200001")
                with self.assertRaises(AccessError):
                    cheque.with_user(user).write({"bank_name": "Other"})

        # Collections and the manager see every cheque.
        for user in (self.collections, self.manager):
            self.assertEqual(Cheque.with_user(user).search([]), cheque)
