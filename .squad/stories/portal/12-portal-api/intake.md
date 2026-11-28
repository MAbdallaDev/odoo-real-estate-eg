# Story intake — 12-portal-api

> **Source:** manual entry (no tracker). Rules, user story and acceptance criteria below are pasted
> from `docs/business-requirements.md` (v1.1 scope change, 2026-11-28). If they ever disagree, that
> document wins.

---

## Feature

- **Feature name (display):** Customer portal (addon `real_estate_eg_portal`)
- **Feature slug (folder under `plans/`):** `portal`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `12-portal-api`

---

## Title

Customer portal REST API (v1.1)

---

## Description

Customers get a JSON REST API under `/api/v1/`: they list the available units, request a
reservation (the Story 11 flow then runs unchanged in Odoo) and follow their reservations,
contracts and installments. It lives in a **new addon, `real_estate_eg_portal`** (depends on
`real_estate_eg` and `portal`), so the backend works without it.

The customer screens (OWL, served by Odoo under `/my/...`) are Story 13, not this story.

**Prime constraint (maintainer):** v1.0.1 is published and Story 11 is merged. No file of
`real_estate_eg` changes; the 107 v1 tests and the Story 11 tests pass **unchanged**.

### Decisions (maintainer, 2026-11-28)

- **Authentication: Odoo API keys** (`res.users.apikeys`), sent as `Authorization: Bearer <key>`,
  checked by Odoo 19's `auth="bearer"` routes. Rejected: JWT (a new library, a signing secret to
  protect, refresh tokens and revocation written by us instead of Odoo's tested code).
- **Customers are Odoo portal users** (`base.group_portal`) linked to their contact. Rejected:
  internal users (backend access, a licence each in Enterprise), our own customer table (the API
  would run as one technical user with `sudo()`, so Odoo security would protect nothing).
  Later, on top of portal users: a contract link without login (`access_token`), login by mobile
  number + OTP (Chapter 7).
- **Keep it simple and additive**: nothing in `real_estate_eg` is edited.

---

## Acceptance criteria

### User stories

**US-15 — Follow my purchase online *(v1.1)***
*As a **customer**, I want to see the available units, ask for a reservation and follow my
reservations, contracts and installments online, so that I do not have to call the sales office for
each step.*

### Business rules

BR-55 to BR-58, as written in `docs/business-requirements.md` §1.2 "Customer portal API (v1.1)".
In short:

| ID | Rule |
|---|---|
| BR-55 | Customer = portal user linked to their contact; API key in `Authorization: Bearer`; staff keys refused. |
| BR-56 | A customer reads only their own reservations, contracts, schedule lines, and units that are available or theirs; read only; Odoo access rights + record rules, never `sudo()`. |
| BR-57 | A request for an available unit follows BR-47–BR-51; note + identity kept on the request for the agent; one open reservation per unit, 5 open at most; creating it is the only `sudo()`. |
| BR-58 | JSON under `/api/v1/`; pagination; `{"error": {"code", "message"}}` with 400/401/403/404/409/422/500, no traceback; not yours = 404; OpenAPI at `/api/v1/openapi.json`. |

### Acceptance criteria (from the business document)

- **AC-15.1** Available units only, paginated, filtered by project, bedrooms and unit type; a unit
  on hold for another customer is not shown.
- **AC-15.2** No key or an invalid key → 401; a staff user's key → 403.
- **AC-15.3** A request → requested, the customer's, assigned to the project's agent with an
  activity, unit still available. Not available / duplicate / sixth open request → 409; invalid
  values → 400 / 422, nothing created.
- **AC-15.4** A customer reads their own reservations, contracts and installments; customer B's are
  not found for A and never in A's lists; customers write nothing.
- **AC-15.5** Errors, including an unknown `/api/v1/` path, are JSON with the right HTTP code.
- **AC-15.6** The OpenAPI file describes every endpoint.
- **AC-15.7** Staff rights and v1 / US-14 behaviour unchanged (suites pass unchanged).

### Endpoints

| Method | Path | AC |
|---|---|---|
| GET | `/api/v1/units`, `/api/v1/units/<id>` | AC-15.1 |
| GET | `/api/v1/reservations`, `/api/v1/reservations/<id>` | AC-15.4 |
| POST | `/api/v1/reservations` | AC-15.3 |
| GET | `/api/v1/contracts`, `/api/v1/contracts/<id>` | AC-15.4 |
| GET | `/api/v1/installments` (`contract_id`, `overdue`) | AC-15.4 |
| GET | `/api/v1/openapi.json` (public) | AC-15.6 |

---

## Dependencies

- **Blocked by / related ids:** 11-reservations (the reservation model and flow), 06-record-rules
  (rule pattern).

## Technical hints (optional)

- `auth="bearer"` (Odoo 19, `ir.http._auth_method_bearer`): a valid key runs the request as its
  owner; no key and no session → 401.
- `ir.http._handle_error` inherited for `/api/v1/` paths only: JSON for 401 / 404 / 500.
- Controllers catch the expected errors themselves (Odoo logs a warning for each `UserError` that
  leaves a controller, and CI fails on any warning) and run in a savepoint.
- Portal ACL (read) + record rules with `child_of [user.commercial_partner_id.id]`, as Odoo's
  `sale_order_rule_portal`.
- Tests: `HttpCase` with real HTTP calls and real API keys.

## Out of scope

- The OWL screens under `/my/...` (Story 13). Note: `auth="bearer"` accepts a browser session only
  for top-level page navigation, so Story 13 decides how its screens call the API (e.g. a session
  route with a CSRF header).
- E-mails to the customer (the customer is not made a follower of the request).
- Online payment, a contract link without login, login by mobile + OTP (Chapter 7).
- Rate limiting (put it in front of Odoo, in the reverse proxy).
- Demo data (Story 14).
