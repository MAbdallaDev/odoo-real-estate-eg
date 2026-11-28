# 11 — Reservations (v1.1)

Why the reservation is built the way it is. Spec: US-14, BR-47–BR-54.

## A separate model, not a new contract state

The obvious shortcut was a `reservation` state before `draft` on the contract. It was rejected:

- The contract's states, its unique index (BR-04), its schedule and its invoices are the heart of
  v1. A new first state would touch every one of them and every test that walks them.
- A reservation has its own life (several requests may wait on one unit, holds expire, requests are
  rejected) that a contract never has.
- A separate record keeps the promise of v1.1: **a unit with no reservation behaves exactly as in
  v1.** The v1 test suite runs unchanged to prove it.

## The unit status reads reservations last

`real.estate.unit._compute_state` (BR-03) keeps its v1 branch first: if a contract that is not
cancelled exists, it alone decides the status. Only when there is none does it look for a held
reservation (`on_hold` for agent confirmed, `reserved` for reserved). So the new code cannot change
the status of any unit that has, or had, a contract under v1 rules.

## One held reservation per unit, in the database

Same idea as BR-04 for contracts: a partial unique index
`(unit_id) WHERE state IN ('agent_confirmed', 'reserved')`. Two agents pressing **Confirm** at the
same moment cannot both win. The Python check before it only gives a clearer message.

## Contracts respect holds

`real.estate.contract.create()` / `write()` call `_check_unit_not_held()`: **no contract on a held
unit**, for any customer. The reservation's **Create Contract** first moves the reservation to
converted (so the unit is no longer held), then creates the contract as the current user with all
the v1 checks, then writes the link both ways as superuser. If the contract fails, the whole call
rolls back and the reservation stays reserved. `reservation_id` is dropped from any create values
and refused in any non-superuser write, so no client can attach a contract to a reservation by hand.

Two earlier versions were closed by the review: one allowed a direct contract for the reservation's
own customer (it left the reservation held beside a live contract), the next trusted a context key
(a client can send any context over RPC). The check searches as superuser (the agent may not see
another agent's reservation) and names only the reservation's reference. Without a held reservation
it finds nothing and v1 behaviour is untouched.

## The reservation amount is an ordinary payment

جدية الحجز could have been a schedule line or a deduction inside the schedule generator. Both would
change BR-14–BR-20, the most tested arithmetic in the module. Instead the customer pays an ordinary
Odoo **customer payment**, which stays as the customer's credit; when the down-payment invoice is
posted, Odoo offers that credit and the accountant reconciles it. The down payment is then paid in
two parts without the schedule knowing anything about reservations.

The reservation only checks, at the manager's **Reserve**, that a posted payment from the same
customer of at least the amount is linked. The payment field is an accounting field
(`groups="account.group_account_invoice"`); managers and agents see a computed
`amount_received` instead, read as superuser.

## Who does what

- The project carries **one agent** (`real.estate.project.user_id`). The request is assigned to that
  agent when it is made (computed from the unit, stored, not from the project's current agent, so
  changing the project's agent later does not move old reservations). No agent: unassigned, for the
  managers.
- `write()` refuses `state` and `contract_id` to everyone but the superuser, so the payment check
  cannot be skipped by writing the state over RPC; one payment secures one reservation.
- `write()` enforces field rights, the way `real.estate.cheque.write()` enforces its transitions: a
  manager edits anything but the state; an agent edits their own request before confirming it; an
  accountant only links the payment. State changes go through the buttons, which check the role and
  then write as superuser; `write()` still checks the transition for every caller (BR-48).

## Expiry has its own job

`_cron_expire` runs in its own `ir.cron` instead of becoming a step of the v1 nightly job, so the
v1 job's code and order (business document §5.5) stay as they were. A hold lasts until the end of
`date_expiry`; the job expires it the next night.
