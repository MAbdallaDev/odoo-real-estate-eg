from ast import literal_eval

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo import fields
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

        # The contract's Cheques button counts and opens under the same rules.
        self.assertEqual(self.contract.with_user(self.agent_a).cheque_count, 1)
        self.assertEqual(self.contract.with_user(self.accountant).cheque_count, 1)
        action = self.contract.with_user(self.agent_a).action_view_cheques()
        self.assertEqual(
            Cheque.with_user(self.agent_a).search(action["domain"]), cheque
        )

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

    # ------------------------------------------------------------------
    # AC-13.4 / BR-42: cheque status is information only
    # ------------------------------------------------------------------

    LINE_FIELDS = [
        "state",
        "amount_paid",
        "amount_residual",
        "is_overdue",
        "days_past_due",
        "late_fee_accrued",
        "aging_bucket",
    ]

    def _snapshot(self, line):
        """What accounting and the nightly job decide, read as collections."""
        return line.with_user(self.collections).read(self.LINE_FIELDS)[0] | {"id": 0}

    def test_ac_13_4_status_only(self):
        # A twin of example A on an identical unit, with no cheque at all.
        twin_unit = self.make_unit("HNC-B07-0303")
        twin_unit.list_price = self.unit_3br.list_price
        with freeze_time("2027-01-10"):
            twin = self._confirmed(
                self.add_schedule(self.create_contract(unit=twin_unit), "2027-01-10")
            )
        with freeze_time("2027-04-10"):
            (self.contract | twin)._invoice_due_lines(fields.Date.today())
        twin_line = twin.installment_ids.filtered(lambda x: x.number == 1)
        self.assertEqual(self.line.amount, twin_line.amount)
        Move = self.env["account.move"].sudo()

        # A cheque is recorded, deposited and cleared; no entry is created.
        moves = Move.search_count([])
        with freeze_time("2027-04-15"):
            cleared = self._record(self.collections, amount=self.line.amount)
            cleared.with_user(self.collections).action_deposit()
            cleared.with_user(self.collections).action_clear()
        self.assertEqual(Move.search_count([]), moves, "no entry for a cheque")
        # The line is still owed, and the nightly job still finds it late.
        self._night("2027-05-20")
        snapshot = self._snapshot(self.line)
        self.assertEqual(snapshot, self._snapshot(twin_line))
        self.assertEqual(snapshot["state"], "invoiced")
        self.assertTrue(snapshot["is_overdue"])
        self.assertGreater(snapshot["late_fee_accrued"], 0)

        # A replacement that bounces changes nothing either.
        moves = Move.search_count([])
        with freeze_time("2027-05-25"):
            bounced = self._record(self.collections, name="100002")
            bounced.with_user(self.collections).action_deposit()
            bounced.with_user(self.collections).action_bounce()
        self.assertEqual(Move.search_count([]), moves, "no entry for a bounce")
        self._night("2027-06-20")
        self.assertEqual(self._snapshot(self.line), self._snapshot(twin_line))

        # Only a payment in accounting pays the line (BR-24).
        self._pay(self.line, self.line.amount, "2027-06-25")
        self.assertEqual(self.line.state, "paid")
        self.assertEqual(twin_line.state, "invoiced")

    # ------------------------------------------------------------------
    # AC-13.5: To Deposit = held cheques dated today or earlier
    # ------------------------------------------------------------------

    def test_ac_13_5_to_deposit(self):
        def cheque(number, day):
            return self._record(self.collections, name=number, date=day)

        yesterday = cheque("1", "2027-04-09")
        today = cheque("2", "2027-04-10")
        cheque("3", "2027-04-11")  # tomorrow: not yet
        deposited = cheque("4", "2027-04-01")
        deposited.with_user(self.collections).action_deposit()
        bounced = cheque("5", "2027-04-01")
        bounced.with_user(self.collections).action_deposit()
        bounced.with_user(self.collections).action_bounce()

        action = self.env.ref("real_estate_eg.real_estate_cheque_action_to_deposit")
        Cheque = self.env["real.estate.cheque"].with_user(self.collections)
        with freeze_time("2027-04-10"):
            to_deposit = Cheque.search(literal_eval(action.domain))
        # Oldest first, the model's order.
        self.assertEqual(to_deposit.ids, (yesterday | today).ids)

    # ------------------------------------------------------------------
    # BR-40: picking the schedule line. Typing in the cheque form's Schedule
    # Line field runs name_search on the installment, whose `name` is computed
    # and translated; before _rec_names_search that raised "Cannot convert
    # real.estate.installment.name to SQL because it is not stored".
    # ------------------------------------------------------------------

    def test_schedule_line_name_search(self):
        Line = self.env["real.estate.installment"].with_user(self.collections)

        # Typing the line's own label finds nothing, but must not raise: the
        # label is computed per language, so it is not in the database.
        self.assertEqual(Line.name_search("Installment 1"), [])

        # Typing the contract's reference finds that contract's lines, and only
        # those. A second contract keeps its lines out of the result.
        with freeze_time("2027-01-31"):
            other = self._confirmed(self.add_schedule(self._example_c(), "2027-01-31"))
        found = Line.name_search(self.contract.name)
        self.assertEqual(
            set(dict(found)), set(self.contract.installment_ids.ids), "its own lines"
        )
        self.assertFalse(
            set(dict(found)) & set(other.installment_ids.ids), "not another contract's"
        )

        # The dropdown's own call: no search text at all.
        self.assertTrue(Line.name_search(""), "the empty picker still lists lines")
