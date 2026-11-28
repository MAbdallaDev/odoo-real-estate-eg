# 12 — Customer portal REST API (v1.1)

- **Feature:** `portal`
- **Intake:** `.squad/stories/portal/12-portal-api/intake.md`
- **Branch:** `story/12-portal-api`, pull request into **`release/1.1`** (never `main`)
- **Status:** code and tests written 2026-11-28; CI green on the branch; not yet tested locally by
  the maintainer

---

## Prerequisites

- `story/12-portal-api` created from `origin/release/1.1` at `22663d9` (Story 11 merged).
- No local Odoo on the current laptop: tests run in GitHub CI. Local checks before every push:
  `py -3.12 -m pre_commit run --all-files`.
- Odoo 19 symbols used were read from `odoo/odoo` branch `19.0` at
  `aa255c890a231708f4b16a467edf9a8235b0020a`: `ir.http._auth_method_bearer`,
  `ir.http._handle_error`, `Request.make_json_response`, `http.route(save_session=...)`,
  `res.users.apikeys._generate()`, `res.users._is_portal()`, `BaseModel.has_access()`,
  `HttpCase.url_open()`.

## Story Goal

US-15: customers list available units, request a reservation and read their own reservations,
contracts and installments over a JSON REST API, through Odoo security. BR-55 to BR-58.

**Prime constraint:** no file of `real_estate_eg` changes. No existing test is edited.

## What changes outside the new addon (and why it is safe)

| File | Change | Why v1 and Story 11 are unaffected |
|---|---|---|
| `docker/docker-compose.ci.yml`, `Makefile` | install and test `real_estate_eg,real_estate_eg_portal` | `real_estate_eg`'s tests run exactly as before, in the same database |
| `scripts/check_odoo_log.sh` | also requires the portal addon's tests to have run, when it is installed | the old checks are unchanged |
| `scripts/check_us_tests.sh` | searches the `test_*.py` files of every addon (US-15's tests are in the new addon) | every US-01–US-14 test is still found |
| `docs/business-requirements.md` | US-15, BR-55–BR-58, actor row, story map, Chapter 7 rows | spec only |

New addon `addons/real_estate_eg_portal/`:

| File | What |
|---|---|
| `controllers/main.py` | the endpoints, the `api_endpoint` wrapper (portal only, JSON errors, savepoint), serializers |
| `controllers/openapi.py` | the OpenAPI 3 description |
| `models/ir_http.py` | `_handle_error` for `/api/v1/` paths: JSON 401 / 404 / 500 |
| `models/real_estate_reservation.py` | `customer_nationality`, `customer_national_id`, `customer_passport_number` (BR-57); `note` and contract `at_risk` for employees only; customers cannot post on the chatter (BR-56) |
| `security/ir.model.access.csv`, `security/ir_rules.xml` | portal: read only, own rows (BR-56) |
| `views/real_estate_reservation_views.xml` | the three identity fields on the reservation form, read only |
| `tests/test_portal_api.py` | `HttpCase` tests below |

## Steps

1. Spec: US-15, BR-55–BR-58, actor row, story map, Chapter 7. **Done.**
2. Addon skeleton, portal ACL and record rules. **Done.**
3. `ir.http` JSON error handler, controllers, OpenAPI. **Done.**
4. Tests (`HttpCase`, real keys, real HTTP). **Done.**
5. Independent review (verification agent) against `origin/release/1.1`: v1 / Story 11 unchanged,
   no leak between customers. Fixed: customers could post on the staff chatter (now needs write
   for non-employees); internal fields `note` (reservation) and `at_risk` (contract) readable by
   RPC (now employees only); the unit rule kept units of rejected requests; lock against two
   parallel requests; `page` capped; redirects left to Odoo. **Done.**
6. CI green on `story/12-portal-api`: lint + the full suite (v1 + Story 11 + Story 12), clean log.
7. Maintainer installs locally, makes a portal user and an API key, and calls the API by hand
   (curl or the OpenAPI file in Swagger UI). **Pending (rule 1).**

## Tests

| Test | Covers |
|---|---|
| `test_us_15_list_available_units` | AC-15.1, BR-58 pagination |
| `test_ac_15_1_unit_on_hold_is_hidden` | AC-15.1, BR-50 |
| `test_ac_15_1_unit_of_closed_request_is_hidden` | AC-15.1, BR-56 (review fix) |
| `test_ac_15_2_authentication` | AC-15.2, BR-55 (auth failure, staff refused) |
| `test_ac_15_3_request_a_reservation` | AC-15.3, BR-57 (happy path) |
| `test_ac_15_3_refused_requests` | AC-15.3, BR-49, BR-57 limits |
| `test_ac_15_3_validation_errors` | AC-15.3, BR-58 (validation errors, nothing created) |
| `test_ac_15_4_my_contracts_and_installments` | AC-15.4 |
| `test_ac_15_4_customer_a_cannot_read_customer_b` | AC-15.4, BR-56 (permission denied) |
| `test_ac_15_4_portal_rights_are_read_only` | AC-15.4, AC-15.7 (ORM level, internal fields, staff rule untouched) |
| `test_ac_15_4_customer_cannot_post_on_the_chatter` | AC-15.4, BR-56 (review fix) |
| `test_ac_15_5_errors_are_json` | AC-15.5 |
| `test_ac_15_6_openapi_lists_every_route` | AC-15.6 |
| **the v1 and Story 11 tests, unchanged** | AC-15.7 |

## Done Criteria

- [ ] AC-15.1 – AC-15.6 each proven by the tests above, green in CI.
- [ ] AC-15.7: `git diff origin/release/1.1 -- addons/real_estate_eg/` is empty.
- [ ] CI log clean (`scripts/check_odoo_log.sh`: no warning or error; both addons' tests ran).
- [ ] Maintainer's local check: portal user + API key, each endpoint by hand, customer A cannot
  see customer B.
