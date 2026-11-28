# Story intake — 13-portal-owl

> **Source:** manual entry (no tracker). Rules, user story and acceptance criteria below are pasted
> from `docs/business-requirements.md` (v1.1 scope change, 2026-11-28). If they ever disagree, that
> document wins.

---

## Feature

- **Feature name (display):** Customer portal (addon `real_estate_eg_portal`)
- **Feature slug (folder under `plans/`):** `portal`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `13-portal-owl`

---

## Title

Customer screens in OWL under `/my/...` (v1.1)

---

## Description

The customer gets pages in Odoo's portal, from the login to a reservation request and after:
cards on the portal home (`/my`), the available units with a request form, their reservations,
their contracts, and one contract with its installment schedule. Each page is an **OWL component**
that calls the **Story 12 API** through one API service.

Odoo 19's `auth="bearer"` accepts a browser session only for a top-level page navigation, not for
`fetch()`, so the API gets its own auth method that also accepts the portal session.

**Prime constraint (maintainer):** no file of `real_estate_eg` changes; the v1, Story 11 and
Story 12 tests pass **unchanged**; API-key clients see no change.

### Decisions (maintainer, 2026-11-28)

- **Auth: Option A.** Our own auth method on the same `/api/v1/` routes: a Bearer key if sent
  (exactly as today), otherwise the logged-in portal user's session, with the CSRF token in the
  `X-CSRF-Token` header for POST. One API for both clients. Rejected: separate jsonrpc routes
  (every endpoint twice), an API key in the browser (a stolen key works anywhere), QWeb pages
  without the API (no OWL).
- **Scope:** every page from the login to the request and after (maintainer: "build all the pages
  of the portal, from the moment the user logs in until they reserve"). A clickable mockup of the
  pages was shown first (fake data, private, not in the repository).
- **Login:** Odoo's own `/web/login`; the agent gives the customer portal access from the contact.

---

## Acceptance criteria

### User story

**US-16 — Use the portal in my browser *(v1.1)***
*As a **customer**, I want pages in the developer's portal where I see the available units, send a
reservation request and follow my reservations, contracts and installments, so that I do not need
an API key or another app.*

### Business rules

| ID | Rule |
|---|---|
| BR-59 | Same API with the browser session; `Authorization` header → BR-55 unchanged; session POST needs the page's CSRF token in `X-CSRF-Token` (else 403 `csrf_failed`); no session 401; staff 403; no key in the browser. |
| BR-60 | Portal pages under `/my/real-estate/` (units + request form, my reservations, my contracts, one contract + schedule), cards on `/my` with counts; each page one OWL component reading through the API; visitors → login, staff → `/my`, another customer's contract → not found. |

BR-55 is amended: the portal session is the only other way in.

### Acceptance criteria (from the business document)

- **AC-16.1** Session reads work; POST without / with a wrong / with another session's token →
  403 JSON, nothing created; with the page's token → created. No session 401, staff session 403.
  API-key calls unchanged.
- **AC-16.2** The four pages open for a customer with their component and assets; the units page
  gets projects and unit types. Visitors → login, staff → `/my`, B's contract → 404.
  *(manual: the form, lists and schedule in a browser.)*
- **AC-16.3** Home cards with the customer's own counts; staff: no card, 0.
- **AC-16.4** v1, US-14 and US-15 suites pass unchanged.

### Pages

| URL | Component | Calls |
|---|---|---|
| `/my` (cards) | — (QWeb, Odoo's counters) | `/my/counters` |
| `/my/real-estate/units` | `UnitList` + `ReserveForm` | `GET /units`, `POST /reservations` |
| `/my/real-estate/reservations` | `ReservationList` | `GET /reservations` |
| `/my/real-estate/contracts` | `ContractList` | `GET /contracts` |
| `/my/real-estate/contracts/<id>` | `ContractDetail` | `GET /contracts/<id>`, `GET /installments` |

---

## Dependencies

- **Blocked by / related ids:** 12-portal-api (the API, merged into `release/1.1`, PR #18).

## Technical hints (optional)

- `ir.http._auth_method_<name>` is how Odoo picks an auth method by the route's `auth=` value;
  `request.validate_csrf()` checks a token against the session.
- OWL in the portal: `<owl-component name="…" props="…"/>` + `registry.category("public_components")`
  (Odoo 19, `web/static/src/public/public_component_interaction.js`).
- Home cards: `portal.portal_docs_entry` + `_prepare_home_portal_values(counters)`.
- CI has no Chrome: a JS tour would log "Chrome executable not found" (a WARNING, which fails CI),
  so the browser side is checked by hand; CI checks the server side and that the assets are served.

## Out of scope

- JS / tour tests in CI (needs Chrome in the CI image; a separate decision).
- Arabic translation of the pages (`i18n/ar.po`), online payment, cancelling a request from the
  portal, documents (contract PDF) on the portal, e-mails to the customer.
- Making customers portal users in bulk (the agent grants portal access per contact, as Odoo does).
