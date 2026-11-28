from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import RealEstateCommon


@tagged("post_install", "-at_install")
class TestReservation(RealEstateCommon):
    """US-14 (v1.1): reserve a unit before the contract. BR-47 to BR-54.

    Horizon New Cairo's agent is agent A and its reservation amount is
    100,000 EGP; Palm Shores Sahel has no agent. Hold days: 3 (the default)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project.write({"user_id": cls.agent_a.id, "reservation_amount": 100_000})
        cls.project_pss = cls.env["real.estate.project"].create(
            {"name": "Palm Shores Sahel", "code": "PSS", "reservation_amount": 50_000}
        )
        cls.unit_pss = cls.env["real.estate.unit"].create(
            {
                "code": "PSS-C01-0004",
                "project_id": cls.project_pss.id,
                "unit_type": "chalet",
                "bedrooms": 2,
                "area": 110,
                "list_price": 4_950_000,
            }
        )

    # Helpers

    def _request(self, user=None, unit=None, partner=None):
        return (
            self.env["real.estate.reservation"]
            .with_user(user or self.agent_a)
            .create(
                {
                    "partner_id": (partner or self.customer_eg).id,
                    "unit_id": (unit or self.unit_3br).id,
                }
            )
        )

    def _held(self, reservation=None):
        reservation = reservation or self._request()
        reservation.with_user(self.agent_a).action_agent_confirm()
        return reservation

    def _link_payment(self, reservation, amount=100_000, partner=None):
        """BR-52: an ordinary posted customer payment, linked by the accountant."""
        payment = self.init_payment(
            amount,
            post=True,
            date=fields.Date.today(),
            partner=partner or reservation.partner_id,
        )
        reservation.with_user(self.accountant).payment_id = payment
        return payment

    def _reserved(self, reservation=None):
        reservation = self._held(reservation)
        self._link_payment(reservation)
        reservation.with_user(self.manager).action_reserve()
        return reservation

    # AC-14.1

    def test_us_14_request_goes_to_project_agent(self):
        """US-14 / AC-14.1: a request starts requested, is assigned to the
        project's agent with an activity, and leaves the unit available."""
        reservation = self._request()
        self.assertEqual(reservation.state, "requested")
        self.assertEqual(reservation.user_id, self.agent_a)
        self.assertEqual(reservation.amount, 100_000)
        self.assertTrue(reservation.name.startswith("RES/"))
        self.assertEqual(reservation.sudo().activity_ids.user_id, self.agent_a)
        self.assertEqual(self.unit_3br.state, "available")

    def test_ac_14_1_request_refused_on_unit_not_available(self):
        self.create_contract(unit=self.unit_2br)  # draft: the unit is reserved
        with self.assertRaisesRegex(UserError, "not available"):
            self._request(unit=self.unit_2br)

    def test_ac_14_1_several_requests_may_wait(self):
        first = self._request()
        second = self._request(partner=self.customer_foreign)
        self.assertEqual((first | second).mapped("state"), ["requested", "requested"])
        self.assertEqual(self.unit_3br.state, "available")

    # AC-14.2

    def test_ac_14_2_agent_confirm_puts_unit_on_hold(self):
        with freeze_time("2027-03-01 12:00"):
            reservation = self._held()
        self.assertEqual(reservation.state, "agent_confirmed")
        self.assertEqual(self.unit_3br.state, "on_hold")
        self.assertEqual(reservation.date_expiry, fields.Date.to_date("2027-03-04"))

    def test_ac_14_2_hold_days_is_a_company_setting(self):
        self.env.company.re_reservation_hold_days = 7
        with freeze_time("2027-03-01 12:00"):
            reservation = self._held()
        self.assertEqual(reservation.date_expiry, fields.Date.to_date("2027-03-08"))

    def test_ac_14_2_one_held_reservation_per_unit(self):
        first = self._request()
        second = self._request(partner=self.customer_foreign)
        self._held(first)
        with self.assertRaisesRegex(UserError, "already held"):
            second.with_user(self.agent_a).action_agent_confirm()
        # And no new request on a unit on hold (BR-50).
        with self.assertRaisesRegex(UserError, "not available"):
            self._request(partner=self.customer_company)

    # AC-14.3

    def test_ac_14_3_agent_sees_only_own(self):
        reservation = self._request()
        Reservation = self.env["real.estate.reservation"]
        self.assertFalse(Reservation.with_user(self.agent_b).search([]))
        with self.assertRaises(AccessError):
            reservation.with_user(self.agent_b).action_agent_confirm()
        with self.assertRaises(AccessError):
            self._request(user=self.agent_b)  # not the project's agent

    def test_ac_14_3_project_without_agent_goes_to_manager(self):
        reservation = self._request(user=self.manager, unit=self.unit_pss)
        self.assertFalse(reservation.user_id)
        self.assertFalse(reservation.sudo().activity_ids)
        self.assertEqual(reservation.amount, 50_000)
        self.assertNotIn(
            reservation,
            self.env["real.estate.reservation"].with_user(self.agent_a).search([]),
        )
        reservation.with_user(self.manager).action_agent_confirm()
        self.assertEqual(self.unit_pss.state, "on_hold")

    # AC-14.4

    def test_ac_14_4_reserve_needs_the_paid_amount(self):
        reservation = self._held()
        as_manager = reservation.with_user(self.manager)
        with self.assertRaisesRegex(UserError, "Link the customer's payment"):
            as_manager.action_reserve()
        self._link_payment(reservation, amount=50_000)
        with self.assertRaisesRegex(UserError, "less than the reservation amount"):
            as_manager.action_reserve()
        self._link_payment(reservation, partner=self.customer_foreign)
        with self.assertRaisesRegex(UserError, "from this customer"):
            as_manager.action_reserve()
        self._link_payment(reservation)
        self.assertEqual(reservation.with_user(self.manager).amount_received, 100_000)
        with freeze_time("2027-03-02 12:00"):
            as_manager.action_reserve()
        self.assertEqual(reservation.state, "reserved")
        self.assertEqual(self.unit_3br.state, "reserved")
        self.assertEqual(reservation.date_expiry, fields.Date.to_date("2027-03-05"))

    def test_ac_14_4_rights_on_reserve_and_payment(self):
        reservation = self._held()
        payment = self.init_payment(
            100_000, post=True, date=fields.Date.today(), partner=self.customer_eg
        )
        with self.assertRaises(AccessError):
            reservation.with_user(self.agent_a).payment_id = payment
        with self.assertRaises(AccessError):
            reservation.with_user(self.accountant).amount = 1
        self._link_payment(reservation)
        with self.assertRaises(AccessError):
            reservation.with_user(self.agent_a).action_reserve()
        self.assertEqual(reservation.state, "agent_confirmed")

    def test_ac_14_4_amount_fixed_once_reserved(self):
        reservation = self._request()
        reservation.with_user(self.agent_a).amount = 120_000
        self.assertEqual(reservation.amount, 120_000)
        reservation.with_user(self.agent_a).amount = 100_000
        self._reserved(reservation)
        with self.assertRaisesRegex(UserError, "fixed"):
            reservation.with_user(self.manager).amount = 90_000

    # AC-14.5

    def test_ac_14_5_create_contract_converts(self):
        reservation = self._reserved()
        action = reservation.with_user(self.agent_a).action_create_contract()
        contract = self.env["real.estate.contract"].browse(action["res_id"])
        self.assertEqual(contract.state, "draft")
        self.assertEqual(contract.partner_id, self.customer_eg)
        self.assertEqual(contract.unit_id, self.unit_3br)
        self.assertEqual(contract.user_id, self.agent_a)
        self.assertEqual(contract.reservation_id, reservation)
        self.assertEqual(reservation.state, "converted")
        self.assertEqual(reservation.contract_id, contract)
        # From here the unit follows the contract, as in v1.
        self.assertEqual(self.unit_3br.state, "reserved")

    def test_ac_14_5_contract_only_from_reserved(self):
        reservation = self._held()
        with self.assertRaisesRegex(UserError, "only from a reserved"):
            reservation.with_user(self.agent_a).action_create_contract()

    # AC-14.6

    def test_ac_14_6_held_unit_takes_no_other_contract(self):
        reservation = self._held()
        with self.assertRaisesRegex(ValidationError, "Create the contract from"):
            self.create_contract(partner=self.customer_foreign)
        # Not even for the reservation's own customer, nor by passing the
        # reservation by hand: only Create Contract converts it (BR-49).
        with self.assertRaisesRegex(ValidationError, "Create the contract from"):
            self.create_contract(partner=self.customer_eg)
        with self.assertRaisesRegex(ValidationError, "Create the contract from"):
            self.env["real.estate.contract"].with_user(self.agent_a).create(
                {
                    "partner_id": self.customer_eg.id,
                    "unit_id": self.unit_3br.id,
                    "user_id": self.agent_a.id,
                    "reservation_id": reservation.id,
                }
            )

    def test_ac_14_6_held_unit_refuses_moving_a_draft_onto_it(self):
        self._held()
        contract = self.create_contract(
            unit=self.unit_2br, partner=self.customer_foreign
        )
        with self.assertRaisesRegex(ValidationError, "Create the contract from"):
            contract.with_user(self.agent_a).unit_id = self.unit_3br

    # Review fixes: rules that must hold for every caller, not only the form.

    def test_ac_14_4_manager_cannot_write_the_state(self):
        """BR-52: the payment check cannot be skipped by writing the state."""
        reservation = self._held()
        with self.assertRaises(AccessError):
            reservation.with_user(self.manager).write({"state": "reserved"})
        self.assertEqual(reservation.state, "agent_confirmed")

    def test_ac_14_4_one_payment_one_reservation(self):
        first = self._reserved()
        second = self._held(self._request(unit=self.unit_2br))
        second.with_user(self.accountant).payment_id = first.sudo().payment_id
        with self.assertRaisesRegex(UserError, "already used by reservation"):
            second.with_user(self.manager).action_reserve()

    def test_ac_14_3_agent_cannot_choose_the_agent(self):
        """BR-51: the project decides who handles a request. Agent B naming
        themselves on a project with no agent is ignored, so the request is
        unassigned and the agent's own create is refused by the record rule."""
        with self.assertRaises(AccessError):
            self.env["real.estate.reservation"].with_user(self.agent_b).create(
                {
                    "partner_id": self.customer_eg.id,
                    "unit_id": self.unit_pss.id,
                    "user_id": self.agent_b.id,
                }
            )
        # A manager may assign it.
        reservation = (
            self.env["real.estate.reservation"]
            .with_user(self.manager)
            .create(
                {
                    "partner_id": self.customer_eg.id,
                    "unit_id": self.unit_pss.id,
                    "user_id": self.agent_b.id,
                }
            )
        )
        self.assertEqual(reservation.user_id, self.agent_b)

    def test_ac_14_3_agent_cannot_move_request_to_other_project(self):
        reservation = self._request()
        with self.assertRaises(AccessError):
            reservation.with_user(self.agent_a).unit_id = self.unit_pss
        self.assertEqual(reservation.unit_id, self.unit_3br)

    def test_ac_14_1_todo_closed_and_reassigned(self):
        reservation = self._request(user=self.manager, unit=self.unit_pss)
        reservation.with_user(self.manager).user_id = self.agent_b
        todo = reservation.sudo().activity_ids
        self.assertEqual(todo.user_id, self.agent_b)
        reservation.with_user(self.agent_b).action_agent_confirm()
        self.assertFalse(reservation.sudo().activity_ids)

    def test_ac_14_1_reassigning_moves_the_todo(self):
        reservation = self._request()  # agent A's to-do
        reservation.with_user(self.manager).user_id = self.agent_b
        self.assertEqual(reservation.sudo().activity_ids.user_id, self.agent_b)

    def test_ac_14_6_reservation_link_not_writable(self):
        """BR-54: only Create Contract links a contract to its reservation,
        whatever a client sends (values or context)."""
        reservation = self._reserved()
        contract = self.create_contract(unit=self.unit_2br)
        with self.assertRaises(AccessError):
            contract.with_user(self.manager).reservation_id = reservation
        with self.assertRaisesRegex(ValidationError, "Create the contract from"):
            self.env["real.estate.contract"].with_user(self.manager).with_context(
                real_estate_from_reservation=True
            ).create(
                {
                    "partner_id": self.customer_foreign.id,
                    "unit_id": self.unit_3br.id,
                    "reservation_id": reservation.id,
                }
            )

    def test_ac_14_2_two_requests_confirmed_together(self):
        first = self._request()
        second = self._request(partner=self.customer_foreign)
        with self.assertRaisesRegex(UserError, "already held"):
            (first | second).with_user(self.agent_a).action_agent_confirm()

    # AC-14.7

    def test_ac_14_7_nightly_job_expires_held(self):
        with freeze_time("2027-03-01 12:00"):
            old = self._held()
        with freeze_time("2027-03-03 12:00"):
            new = self._held(self._request(unit=self.unit_2br))
        Reservation = self.env["real.estate.reservation"].sudo()
        Reservation._cron_expire(fields.Date.to_date("2027-03-04"))
        self.assertEqual(old.state, "agent_confirmed")  # its last day
        Reservation._cron_expire(fields.Date.to_date("2027-03-05"))
        self.assertEqual(old.state, "expired")
        self.assertEqual(self.unit_3br.state, "available")
        self.assertEqual(new.state, "agent_confirmed")
        self.assertEqual(self.unit_2br.state, "on_hold")

    def test_ac_14_7_requests_never_expire(self):
        reservation = self._request()
        self.env["real.estate.reservation"].sudo()._cron_expire(
            fields.Date.to_date("2099-01-01")
        )
        self.assertEqual(reservation.state, "requested")

    # AC-14.8

    def test_ac_14_8_reject_rights(self):
        request = self._request()
        request.with_user(self.agent_a).action_reject()
        self.assertEqual(request.state, "rejected")
        reserved = self._reserved(self._request(unit=self.unit_2br))
        with self.assertRaises(AccessError):
            reserved.with_user(self.agent_a).action_reject()
        reserved.with_user(self.manager).action_reject()
        self.assertEqual(reserved.state, "rejected")
        self.assertEqual(self.unit_2br.state, "available")

    def test_ac_14_8_final_states_do_not_move(self):
        reservation = self._request()
        reservation.with_user(self.agent_a).action_reject()
        with self.assertRaisesRegex(UserError, "Only a requested"):
            reservation.with_user(self.agent_a).action_agent_confirm()
        with self.assertRaisesRegex(UserError, "already closed"):
            reservation.with_user(self.manager).action_reject()
        with self.assertRaisesRegex(UserError, "cannot go from"):
            reservation.sudo().write({"state": "requested"})

    # AC-14.9

    def test_ac_14_9_unit_without_reservation_as_v1(self):
        """A unit's status still follows its contract alone (BR-03)."""
        self.assertEqual(self.unit_3br.state, "available")
        contract = self.create_contract()
        self.assertEqual(self.unit_3br.state, "reserved")
        contract.with_user(self.agent_a).action_cancel()
        self.assertEqual(self.unit_3br.state, "available")

    def test_ac_14_9_converted_reservation_does_not_hold(self):
        reservation = self._reserved()
        action = reservation.with_user(self.agent_a).action_create_contract()
        contract = self.env["real.estate.contract"].browse(action["res_id"])
        contract.with_user(self.agent_a).action_cancel()
        self.assertEqual(self.unit_3br.state, "available")
