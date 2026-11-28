from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

# BR-48: a reservation's states, in order.
RESERVATION_STATE = [
    ("requested", "Requested"),
    ("agent_confirmed", "Agent Confirmed"),
    ("reserved", "Reserved"),
    ("converted", "Converted"),
    ("rejected", "Rejected"),
    ("expired", "Expired"),
]

# BR-48: the only moves. Converted, rejected and expired are final.
TRANSITIONS = {
    "requested": ("agent_confirmed", "rejected"),
    "agent_confirmed": ("reserved", "rejected", "expired"),
    "reserved": ("converted", "rejected", "expired"),
}

# BR-49 / BR-50: the states that hold a unit for one customer.
HELD_STATES = ("agent_confirmed", "reserved")

# BR-52: a payment counts once it is posted (Odoo 19 account.payment states).
PAYMENT_DONE_STATES = ("in_process", "paid")

# What an agent may edit on their own request before they confirm it.
AGENT_FIELDS = {"partner_id", "unit_id", "amount", "note"}
# Set only by the system: the buttons and the nightly job, never typed.
SYSTEM_FIELDS = {"state", "contract_id"}
# Not given at creation except by a manager (BR-51: the project decides the agent).
MANAGER_CREATE_FIELDS = {"user_id", "date_expiry", "contract_id"}
# BR-52: an accountant only links the customer's payment.
ACCOUNTANT_FIELDS = {"payment_id"}


class RealEstateReservation(models.Model):
    """US-14 / BR-47: a customer's reservation of a unit, before any contract.
    It holds the unit for that customer (BR-49, BR-50) and ends either as a
    contract (BR-54), rejected or expired (BR-53)."""

    _name = "real.estate.reservation"
    _description = "Unit Reservation"
    _inherit = ["mail.thread", "mail.activity.mixin"]  # chatter and activities
    _check_company_auto = True
    _order = "id desc"
    # As on contracts: whoever can read a reservation may log a note on it.
    _mail_post_access = "read"

    # BR-47: reference from a sequence, set in create().
    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        index="trigram",
        default=lambda self: self.env._("New"),
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        index=True,
        tracking=True,
        check_company=True,
    )
    unit_id = fields.Many2one(
        "real.estate.unit",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    project_id = fields.Many2one(related="unit_id.project_id", store=True)
    company_id = fields.Many2one(related="unit_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    # BR-51: the project's agent when the request is made. Depends on the unit
    # only, so a later change of the project's agent does not move old rows.
    user_id = fields.Many2one(
        "res.users",
        string="Sales Agent",
        compute="_compute_user_id",
        store=True,
        precompute=True,
        readonly=False,
        index=True,
        tracking=True,
    )
    # BR-52: the project's fixed amount, editable until reserved.
    amount = fields.Monetary(
        string="Reservation Amount",
        compute="_compute_amount",
        store=True,
        precompute=True,
        readonly=False,
        tracking=True,
    )
    # BR-53: the last day the unit is held.
    date_expiry = fields.Date(string="Hold Until", copy=False, tracking=True)
    # BR-52: the customer's payment of the reservation amount. An accounting
    # field: only accounting users see or link it.
    payment_id = fields.Many2one(
        "account.payment",
        string="Reservation Payment",
        copy=False,
        tracking=True,
        groups="account.group_account_invoice",
        domain="[('partner_id', '=', partner_id), ('payment_type', '=', 'inbound'),"
        " ('state', 'in', ('in_process', 'paid'))]",
    )
    # What the manager sees instead of the payment itself (read as superuser).
    amount_received = fields.Monetary(compute="_compute_amount_received")
    # BR-54: the contract created from this reservation.
    contract_id = fields.Many2one(
        "real.estate.contract", readonly=True, copy=False, index="btree_not_null"
    )
    note = fields.Text()
    # For the form only: managers edit the expiry date (BR-53).
    user_is_manager = fields.Boolean(compute="_compute_user_is_manager")
    state = fields.Selection(
        RESERVATION_STATE,
        string="Status",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        default="requested",
    )

    # BR-49 in the database: one held reservation per unit, even when two
    # users confirm at the same moment (same shape as the contract's BR-04).
    _unit_held_unique = models.UniqueIndex(
        "(unit_id) WHERE state IN ('agent_confirmed', 'reserved')",
        "This unit is already held by another reservation.",
    )
    _amount_not_negative = models.Constraint(
        "CHECK (amount >= 0)", "The reservation amount cannot be negative."
    )

    @api.depends("unit_id")
    def _compute_user_id(self):
        for reservation in self:
            reservation.user_id = reservation.unit_id.project_id.user_id

    @api.depends("unit_id")
    def _compute_amount(self):
        for reservation in self:
            reservation.amount = reservation.unit_id.project_id.reservation_amount

    @api.depends_context("uid")
    def _compute_user_is_manager(self):
        self.user_is_manager = self._is_manager()

    @api.depends("payment_id.amount", "payment_id.state")
    def _compute_amount_received(self):
        for reservation in self:
            payment = reservation.sudo().payment_id
            reservation.amount_received = (
                payment.amount if payment.state in PAYMENT_DONE_STATES else 0.0
            )

    # ------------------------------------------------------------------
    # Create and write
    # ------------------------------------------------------------------

    def _check_units_available(self, units):
        """BR-49 / AC-14.1: a request only for an available unit."""
        for unit in units:
            if unit.state != "available":
                raise UserError(
                    self.env._("Unit %(unit)s is not available.", unit=unit.code)
                )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_units_available(
            self.env["real.estate.unit"].browse(
                [vals["unit_id"] for vals in vals_list if vals.get("unit_id")]
            )
        )
        today = fields.Date.context_today(self)
        is_manager = self.env.su or self._is_manager()
        for vals in vals_list:
            # AC-14.1: a new reservation is always a request.
            vals["state"] = "requested"
            # BR-51: an agent cannot choose who handles the request.
            if not is_manager:
                for field in MANAGER_CREATE_FIELDS:
                    vals.pop(field, None)
            if vals.get("name", self.env._("New")) == self.env._("New"):
                unit = self.env["real.estate.unit"].browse(vals.get("unit_id"))
                vals["name"] = self.env["ir.sequence"].with_company(
                    unit.company_id
                ).next_by_code(
                    "real.estate.reservation", sequence_date=today
                ) or self.env._("New")
        reservations = super().create(vals_list)
        # BR-51: the agent gets a to-do; an unassigned request waits for managers.
        reservations._schedule_todo()
        return reservations

    def write(self, vals):
        if not self.env.su:
            self._check_write_rights(vals)
        # BR-48: checked here, not only by hiding buttons, so the rule holds for
        # every caller: RPC, imports, code, and the superuser too.
        if "state" in vals:
            for reservation in self:
                new = vals["state"]
                if new != reservation.state and new not in TRANSITIONS.get(
                    reservation.state, ()
                ):
                    raise UserError(
                        self.env._(
                            "A reservation cannot go from %(old)s to %(new)s.",
                            old=dict(RESERVATION_STATE)[reservation.state],
                            new=dict(RESERVATION_STATE).get(new, new),
                        )
                    )
        if vals.get("unit_id"):
            self._check_units_available(
                self.env["real.estate.unit"].browse(vals["unit_id"])
            )
        reassigned = (
            self.filtered(lambda r: r.user_id.id != vals["user_id"])
            if "user_id" in vals
            else self.browse()
        )
        res = super().write(vals)
        # BR-51: a waiting request moved to another agent moves its to-do too.
        waiting = reassigned.filtered(lambda r: r.state == "requested")
        if waiting:
            waiting.sudo().activity_unlink(["mail.mail_activity_data_todo"])
            waiting._schedule_todo()
        return res

    def _schedule_todo(self):
        for reservation in self.filtered("user_id"):
            reservation.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=reservation.user_id.id,
                summary=self.env._("New reservation request"),
            )

    def _check_write_rights(self, vals):
        """BR-51 / BR-52: who edits what. A manager edits everything but the
        state (buttons only); an agent edits their own request before
        confirming it; an accountant only links the payment."""
        if SYSTEM_FIELDS.intersection(vals):
            raise AccessError(
                self.env._("The status changes only through the reservation's buttons.")
            )
        if {"unit_id", "partner_id"}.intersection(vals) and any(
            r.state != "requested" for r in self
        ):
            raise UserError(
                self.env._(
                    "The customer and the unit can be changed only on a request."
                )
            )
        if "amount" in vals and any(
            r.state not in ("requested", "agent_confirmed") for r in self
        ):
            raise UserError(
                self.env._("The reservation amount is fixed once the unit is reserved.")
            )
        user = self.env.user
        if user.has_group("real_estate_eg.group_real_estate_manager"):
            return
        allowed = set()
        if user.has_group("account.group_account_invoice"):
            allowed |= ACCOUNTANT_FIELDS
        if user.has_group("real_estate_eg.group_real_estate_agent") and all(
            r.state == "requested" and r.user_id == user for r in self
        ):
            allowed |= AGENT_FIELDS
            # BR-51: moving a request to another project's unit would hand it
            # to that project's agent; only a manager does that.
            if vals.get("unit_id"):
                unit = self.env["real.estate.unit"].browse(vals["unit_id"])
                if any(r.project_id != unit.project_id for r in self):
                    raise AccessError(
                        self.env._(
                            "Only a manager can move a request to another project."
                        )
                    )
        if set(vals) - allowed:
            raise AccessError(self.env._("You cannot change this reservation."))

    # ------------------------------------------------------------------
    # State actions (BR-48)
    # ------------------------------------------------------------------

    def _is_manager(self):
        return self.env.user.has_group("real_estate_eg.group_real_estate_manager")

    def _check_manager(self):
        if not self._is_manager():
            raise AccessError(self.env._("Only a sales manager can do this."))

    def _check_agent_or_manager(self):
        """BR-51: the reservation's own agent, or a manager."""
        if not self._is_manager() and any(r.user_id != self.env.user for r in self):
            raise AccessError(
                self.env._("Only the reservation's agent or a manager can do this.")
            )

    def _hold_until(self):
        """BR-53: today + the company's hold days."""
        self.ensure_one()
        return fields.Date.context_today(self) + timedelta(
            days=self.company_id.re_reservation_hold_days
        )

    def _check_unit_can_be_held(self):
        """BR-49: no live contract and no other held reservation on the unit.
        As superuser: the agent's record rules hide other agents' rows, but the
        unit is still taken. The messages name only the other reference."""
        self.ensure_one()
        contract = (
            self.env["real.estate.contract"]
            .sudo()
            .search(
                [("unit_id", "=", self.unit_id.id), ("state", "!=", "cancelled")],
                limit=1,
            )
        )
        if contract:
            raise UserError(
                self.env._(
                    "Unit %(unit)s already has contract %(reference)s.",
                    unit=self.unit_id.code,
                    reference=contract.name,
                )
            )
        held = self.sudo().search(
            [
                ("unit_id", "=", self.unit_id.id),
                ("state", "in", HELD_STATES),
                ("id", "!=", self.id),
            ],
            limit=1,
        )
        if held:
            raise UserError(
                self.env._(
                    "Unit %(unit)s is already held by reservation %(reference)s.",
                    unit=self.unit_id.code,
                    reference=held.name,
                )
            )

    def action_agent_confirm(self):
        """AC-14.2: the agent agreed terms with the customer; the unit is on
        hold until the expiry date."""
        self._check_agent_or_manager()
        if any(r.state != "requested" for r in self):
            raise UserError(
                self.env._("Only a requested reservation can be confirmed.")
            )
        # One at a time: a second request on the same unit in this call then
        # sees the first one held and gets the clear message (BR-49).
        for reservation in self:
            reservation._check_unit_can_be_held()
            # Written as superuser: state is not an editable field for anyone
            # (write() still checks the transition).
            reservation.sudo().write(
                {"state": "agent_confirmed", "date_expiry": reservation._hold_until()}
            )
        self._close_todo()
        return True

    def _payment_error_message(self):
        """BR-52: why the reservation amount does not count as paid, or False."""
        self.ensure_one()
        if self.currency_id.is_zero(self.amount):
            return False
        payment = self.sudo().payment_id
        if not payment:
            return self.env._("Link the customer's payment of the reservation amount.")
        if (
            payment.state not in PAYMENT_DONE_STATES
            or payment.payment_type != "inbound"
            or payment.partner_id.commercial_partner_id
            != self.partner_id.commercial_partner_id
            or payment.currency_id != self.currency_id
        ):
            return self.env._(
                "The linked payment must be a posted payment from this customer."
            )
        # BR-52: one payment secures one reservation.
        other = self.sudo().search(
            [
                ("payment_id", "=", payment.id),
                ("id", "!=", self.id),
                ("state", "in", ("reserved", "converted")),
            ],
            limit=1,
        )
        if other:
            return self.env._(
                "This payment is already used by reservation %(reference)s.",
                reference=other.name,
            )
        if self.currency_id.compare_amounts(payment.amount, self.amount) < 0:
            return self.env._(
                "The linked payment of %(paid)s is less than the reservation amount "
                "%(amount)s.",
                paid=payment.amount,
                amount=self.amount,
            )
        return False

    def action_reserve(self):
        """AC-14.4: the manager confirms once the amount is paid; the hold is
        counted again from today."""
        self._check_manager()
        for reservation in self:
            if reservation.state != "agent_confirmed":
                raise UserError(
                    self.env._(
                        "Only a reservation confirmed by the agent can be reserved."
                    )
                )
            error = reservation._payment_error_message()
            if error:
                raise UserError(error)
        for reservation in self:
            reservation.sudo().write(
                {"state": "reserved", "date_expiry": reservation._hold_until()}
            )
        return True

    def action_reject(self):
        """AC-14.8: the agent rejects before the unit is reserved; after that,
        only a manager. Refunding a paid amount is the accountant's manual step."""
        if any(r.state not in TRANSITIONS for r in self):
            raise UserError(self.env._("This reservation is already closed."))
        if any(r.state == "reserved" for r in self):
            self._check_manager()
        else:
            self._check_agent_or_manager()
        self.sudo().write({"state": "rejected"})
        self._close_todo()
        return True

    def action_create_contract(self):
        """AC-14.5 / BR-54: a draft contract for this customer, unit and agent;
        from here the v1 contract cycle runs unchanged."""
        self.ensure_one()
        self._check_agent_or_manager()
        if self.state != "reserved":
            raise UserError(
                self.env._("A contract is created only from a reserved reservation.")
            )
        # Converted first, so the unit is no longer held when the contract is
        # created (the contract refuses held units). If the contract fails,
        # the whole call is rolled back and the reservation stays reserved.
        self.sudo().write({"state": "converted"})
        # As the current user: the contract's own rights and checks apply.
        contract = self.env["real.estate.contract"].create(
            {
                "partner_id": self.partner_id.id,
                "unit_id": self.unit_id.id,
                "user_id": (self.user_id or self.env.user).id,
            }
        )
        # The link both ways, written by the system only.
        contract.sudo().reservation_id = self
        self.sudo().contract_id = contract
        return {
            "type": "ir.actions.act_window",
            "res_model": "real.estate.contract",
            "res_id": contract.id,
            "view_mode": "form",
        }

    @api.model
    def _cron_expire(self, today=None):
        """BR-53 / AC-14.7: expire held reservations past their expiry date.
        Its own job, so the v1 nightly job is unchanged."""
        today = today or fields.Date.context_today(self)
        expired = self.search(
            [("state", "in", HELD_STATES), ("date_expiry", "<", today)]
        )
        expired.write({"state": "expired"})
        expired._close_todo()
        return expired

    def _close_todo(self):
        """BR-51: the agent's to-do is done once the request is answered."""
        self.sudo().activity_feedback(["mail.mail_activity_data_todo"])
