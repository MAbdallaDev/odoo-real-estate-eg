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

    # ------------------------------------------------------------------
    # AC-13.2 / BR-41: held -> deposited -> cleared or bounced, nothing else
    # ------------------------------------------------------------------

    def _move(self, cheque, button):
        """Press `button` with chatter tracking on (Odoo's test base turns it
        off), then run the tracking, a pre-commit hook, as a real save would.
        Tracking compares a field's value before and after, at each flush, so
        flush before (a create with tracking off marks the record "do not
        track" until then) and after each move."""
        self.env.flush_all()
        self.env.cr.flush()
        getattr(
            cheque.with_context(tracking_disable=False, mail_notrack=False), button
        )()
        self.env.flush_all()
        self.env.cr.flush()

    @staticmethod
    def _tracked_states(cheque):
        """The state changes logged in the cheque's chatter, oldest first."""
        values = (
            cheque.env["mail.tracking.value"]
            .sudo()
            .search(
                [
                    ("mail_message_id.model", "=", cheque._name),
                    ("mail_message_id.res_id", "=", cheque.id),
                    ("field_id.name", "=", "state"),
                ],
                order="id",
            )
        )
        return values.mapped("new_value_char")

    def test_ac_13_2_allowed_moves(self):
        cleared = self._record(self.collections).with_user(self.collections)
        self._move(cleared, "action_deposit")
        self.assertEqual(cleared.state, "deposited")
        self._move(cleared, "action_clear")
        self.assertEqual(cleared.state, "cleared")
        self.assertEqual(self._tracked_states(cleared), ["Deposited", "Cleared"])

        bounced = self._record(self.manager, name="100002").with_user(self.manager)
        self._move(bounced, "action_deposit")
        self._move(bounced, "action_bounce")
        self.assertEqual(bounced.state, "bounced")
        self.assertEqual(self._tracked_states(bounced), ["Deposited", "Bounced"])

    def test_ac_13_2_other_moves_refused(self):
        held = self._record(self.collections, name="1")
        cleared = self._record(self.collections, name="2")
        cleared.with_user(self.collections).action_deposit()
        cleared.with_user(self.collections).action_clear()
        bounced = self._record(self.collections, name="3")
        bounced.with_user(self.collections).action_deposit()
        bounced.with_user(self.collections).action_bounce()

        refused = [
            (held, "cleared"),
            (held, "bounced"),
            (cleared, "held"),
            (cleared, "deposited"),
            (cleared, "bounced"),
            (bounced, "held"),
            (bounced, "deposited"),
            (bounced, "cleared"),
        ]
        buttons = {
            "deposited": "action_deposit",
            "cleared": "action_clear",
            "bounced": "action_bounce",
        }
        for cheque, new in refused:
            old = cheque.state
            # By write(), as the manager and as the superuser...
            for env_cheque in (cheque.with_user(self.manager), cheque.sudo()):
                with (
                    self.subTest(old=old, new=new, su=env_cheque.env.su),
                    self.assertRaises(UserError),
                ):
                    env_cheque.write({"state": new})
            # ...and by the button.
            if new in buttons:
                with self.subTest(button=buttons[new]), self.assertRaises(UserError):
                    getattr(cheque.with_user(self.manager), buttons[new])()
        self.assertEqual(
            (held | cleared | bounced).mapped("state"), ["held", "cleared", "bounced"]
        )

        # What is written on a cheque is fixed once it leaves "held".
        deposited = self._record(self.collections, name="4").with_user(self.collections)
        deposited.write({"amount": 200_000})  # held: a typo can be corrected
        deposited.action_deposit()
        with self.assertRaises(UserError):
            deposited.write({"amount": 214_500})
        self.assertEqual(deposited.amount, 200_000)

    # ------------------------------------------------------------------
    # AC-13.3: a bounced cheque is replaced; its history stays
    # ------------------------------------------------------------------

    def test_ac_13_3_bounced_replaced(self):
        first = self._record(self.collections).with_user(self.collections)
        first.action_deposit()
        first.action_bounce()

        second = self._record(self.collections, name="100002", date="2027-04-20")
        self.assertEqual(second.state, "held")
        line = self.line.with_user(self.collections)
        self.assertEqual(line.cheque_ids, first | second)
        self.assertEqual(first.state, "bounced")
        self.assertEqual(first.name, "100001")

        # Nobody deletes a cheque: the history is kept.
        for user in (self.collections, self.manager):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                first.with_user(user).unlink()
