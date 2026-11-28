# 13 — Customer screens in OWL under `/my/...` (v1.1)

- **Feature:** `portal`
- **Intake:** `.squad/stories/portal/13-portal-owl/intake.md`
- **Branch:** `story/13-portal-owl`, pull request into **`release/1.1`** (never `main`)
- **Status:** code and tests written 2026-11-28; not yet tested locally by the maintainer

---

## Prerequisites

- `story/13-portal-owl` created from `origin/release/1.1` at `f67229a` (Story 12 merged, CI green).
- No local Odoo on the current laptop: tests run in GitHub CI. Local checks before every push:
  `py -3.12 -m pre_commit run --all-files`.
- Odoo 19 symbols used were read from `odoo/odoo` branch `19.0`: `ir.http._authenticate_explicit`
  (calls `_auth_method_<auth>`), `_auth_method_bearer`, `_auth_method_user`, `_get_public_users`,
  `Request.validate_csrf`, `Request.csrf_token`, `web.layout` (`odoo.csrf_token`),
  `PublicComponentInteraction` (`<owl-component>`), `portal.portal_docs_entry`,
  `CustomerPortal._prepare_home_portal_values`, `HttpCase.authenticate`,
  `HttpCase.make_jsonrpc_request`, and `ChromeBrowser.executable` (logs a WARNING without Chrome).

## Story Goal

US-16: customers use the portal in their browser, from `/my` to a reservation request, and follow
their reservations, contracts and installments. BR-59, BR-60.

**Prime constraint:** no file of `real_estate_eg` changes. No existing test is edited. API-key
clients see no change.

## What changes outside the new files (and why it is safe)

| File | Change | Why v1, Story 11 and Story 12 are unaffected |
|---|---|---|
| `models/ir_http.py` | new `_auth_method_re_portal_api`; JSON 403 `csrf_failed`; 401 message mentions login | with an `Authorization` header it calls Odoo's `_auth_method_bearer` unchanged; without a header and without a session it raises the same 401 as before |
| `controllers/main.py` | the routes use `auth="re_portal_api"` instead of `"bearer"` | same as above; endpoints unchanged |
| `controllers/openapi.py` | describes the session scheme | the OpenAPI test compares the file with itself and with the routes, which are unchanged |
| `__manifest__.py`, `README.rst` | name "Customer Portal", version 19.0.1.1.0, pages + assets | — |
| `tests/__init__.py` | imports the new test file | the Story 12 test file is not touched |
| `docs/business-requirements.md` | US-16, BR-59, BR-60, BR-55 amended (session is the other way in), story map, actor row, Chapter 7 row | spec only |

New files in `addons/real_estate_eg_portal/`:

| File | What |
|---|---|
| `controllers/portal.py` | home counters; the four `/my/real-estate/` pages (portal users only) |
| `views/portal_templates.xml` | home cards, breadcrumbs, the page template holding one `<owl-component>` |
| `static/src/js/api_service.js` | the one API service (`real_estate_eg_portal.api`): session cookie, `X-CSRF-Token` on POST, `ApiError` |
| `static/src/js/common.js` | money / date formats, state labels, `Pager` |
| `static/src/js/unit_list.js` | `UnitList`, `ReserveForm` |
| `static/src/js/my_records.js` | `ReservationList`, `ContractList`, `ContractDetail` |
| `static/src/xml/portal_components.xml` | the OWL templates |
| `static/src/scss/portal.scss`, `static/src/img/*.svg` | styles, card icons |
| `tests/test_portal_pages.py` | `HttpCase` tests below |

## Steps

1. Mockup of every page shown to the maintainer (private artifact, fake data). **Done.**
2. Spec: US-16, BR-59, BR-60. **Done.**
3. Auth method + JSON 403 for CSRF; routes switched. **Done.**
4. Portal controllers, templates, OWL components, API service, assets. **Done.**
5. Tests (`HttpCase`, real sessions, real CSRF tokens, the asset bundles). **Done.**
6. Independent review (verification agent) against `origin/release/1.1`.
7. CI green on `story/13-portal-owl`: lint + the full suite (v1 + Story 11 + 12 + 13), clean log.
8. Maintainer installs locally, gives a contact portal access, logs in as the customer and walks
   through every page; sends a request; checks it in the backend. **Pending (rule 1).**

## Tests

| Test | Covers |
|---|---|
| `test_us_16_session_reads_the_api` | AC-16.1, BR-59 (session reads, BR-56 still applies) |
| `test_ac_16_1_session_post_needs_the_csrf_header` | AC-16.1, BR-59 (no / wrong / form-field token refused, page token passes) |
| `test_ac_16_1_token_of_another_session_is_refused` | AC-16.1, BR-59 |
| `test_ac_16_1_anonymous_and_staff_sessions` | AC-16.1, BR-55, BR-59 (401 / 403) |
| `test_ac_16_2_pages_mount_their_component` | AC-16.2, BR-60 |
| `test_ac_16_2_assets_are_in_the_frontend_bundle` | AC-16.2 (JS, templates and SCSS served and compiled) |
| `test_ac_16_2_who_may_open_the_pages` | AC-16.2, BR-60 (login redirect, staff redirect, 404) |
| `test_ac_16_3_home_cards_and_counters` | AC-16.3 |
| **the v1, Story 11 and Story 12 tests, unchanged** | AC-16.4 |

Not in CI: the components running in a browser (no Chrome in the CI image). Checked by hand in
step 8.

## Done Criteria

- [ ] AC-16.1 – AC-16.3 each proven by the tests above, green in CI.
- [ ] AC-16.4: `git diff origin/release/1.1 -- addons/real_estate_eg/ addons/real_estate_eg_portal/tests/test_portal_api.py` is empty.
- [ ] CI log clean (`scripts/check_odoo_log.sh`).
- [ ] Maintainer's local walk-through (step 8).
