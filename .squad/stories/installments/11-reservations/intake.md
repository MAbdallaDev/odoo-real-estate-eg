# Story intake — 11-reservations

> **Source:** manual entry (no tracker). Rules, user story and acceptance criteria below are pasted
> from `docs/business-requirements.md` (v1.1 scope change, 2026-11-28). If they ever disagree, that
> document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `11-reservations`

---

## Title

Reservations before the contract (v1.1)

---

## Description

A customer asks for a unit; the project's agent confirms the request after talking to the customer,
which puts the unit **on hold**; the customer pays the reservation amount (جدية الحجز) as an
ordinary Odoo payment; the manager confirms, and the unit is **reserved**; the agent then creates
the contract, and the v1 cycle runs unchanged. Holds expire after 3 days (a company setting).

This is the backend base for the customer portal (Stories 12 and 13). In this story, staff enter
requests in Odoo; the portal will create them later.

**Prime constraint (maintainer):** v1.0.1 is published. Nothing in v1 may behave differently for a
unit that has no reservation. The 107 v1 tests must pass **unchanged**.

---

## Acceptance criteria

### User stories

**US-14 — Reserve a unit before the contract *(v1.1)***
*As a **sales manager**, I want a customer's request for a unit to go through the project's agent and
my approval, with the reservation amount paid, before a contract is made, so that a unit is never
promised to two customers and every contract starts from a real commitment.*

### Business rules

BR-47 to BR-54, as written in `docs/business-requirements.md` §1.2 "Reservations (v1.1)". In short:

| ID | Rule |
|---|---|
| BR-47 | A reservation is its own record (customer, unit, agent, amount, expiry, status, reference `RES/YYYY/NNNNN`). |
| BR-48 | requested → agent confirmed → reserved → converted; rejected (manager only once reserved); expired. Final: rejected, expired, converted. |
| BR-49 | Requests only for available units; at most one held (agent confirmed / reserved) reservation per unit, in the database; no hold on a unit with a live contract. |
| BR-50 | Unit status: a live contract decides as in v1; else on hold / reserved from the held reservation; else available. |
| BR-51 | One agent per project gets the request (activity); no agent → unassigned, for managers. Agents see only their own reservations. |
| BR-52 | Amount defaults to the project's fixed amount. Reserved only with a linked posted customer payment ≥ amount from the same customer, linked by an accountant; one payment, one reservation. Schedule unchanged. |
| BR-53 | Holds expire after N days (default 3) from each confirmation; manager may change the date; nightly job expires them. |
| BR-54 | Create contract from reserved → draft contract, reservation converted. Held unit: no contract any other way. |

### Acceptance criteria (from the business document)

- **AC-14.1** Given an available unit, a request starts **requested**, is assigned to the project's
  agent with an activity, and leaves the unit **available**. A request for a unit that is not
  available is refused.
- **AC-14.2** Agent confirms → unit **on hold**, expiry = today + hold days (3). A second request on
  the same unit cannot be confirmed.
- **AC-14.3** An agent cannot see or act on another agent's reservation; a project with no agent
  gives an unassigned request handled by a manager.
- **AC-14.4** No reserve without a linked posted payment from the same customer ≥ the amount; with
  it → **reserved**, unit **reserved**, expiry moved. Only an accountant links the payment; an agent
  cannot reserve.
- **AC-14.5** **Create contract** → draft contract for its customer, unit and agent, linked; the
  reservation is **converted**.
- **AC-14.6** Held unit: a contract made any other way is refused, even for the reservation's own
  customer; Create contract is the only way.
- **AC-14.7** The nightly job expires held reservations past their date and frees the unit; others
  are untouched.
- **AC-14.8** Agent rejects requested / agent-confirmed; only a manager rejects reserved. Final
  states cannot move.
- **AC-14.9** A unit with no reservations behaves exactly as in v1 (the v1 suite passes unchanged).

### Reference data (test fixtures)

- Hold days: **3** (company setting `re_reservation_hold_days`).
- Horizon New Cairo reservation amount: **100,000 EGP** (project field `reservation_amount`).
- Rights: agent W (own, before reserved, create contract); manager W (all, reserve, reject reserved);
  collections R; accountant R + link the payment.

---

## Dependencies

- **Blocked by / related ids:** 02-core-models (unit state, contract BR-04), 04-accounting-link
  (payments), 06-record-rules (rule pattern).

## Technical hints (optional)

- New model `real.estate.reservation` (`mail.thread`, `mail.activity.mixin`), state changed only by
  buttons that check the transition (same as the cheque model).
- Unit: `selection_add`-free in-place change: add `on_hold` to the state selection and
  `reservation_ids`; `_compute_state` reads reservations **only when there is no live contract**.
- Held-reservation uniqueness: `models.UniqueIndex("(unit_id) WHERE state IN ('agent_confirmed', 'reserved')")`, as the contract's BR-04 index.
- Payment: `account.payment` field visible to `account.group_account_invoice` only; the manager sees a
  computed "amount received" read as superuser.
- Expiry: its own `ir.cron` (`_cron_expire`), so the v1 nightly job is not edited.

## Out of scope

- The portal, the REST API and customer logins (Stories 12–13).
- Emails to the customer (Story 12, when customers have portal users).
- Deducting the reservation amount inside the schedule (not needed, BR-52).
- Refunding a rejected reservation's payment (the accountant does it by hand, as for cancellations).
- Demo data for reservations (Story 14).
