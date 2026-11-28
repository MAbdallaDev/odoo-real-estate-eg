# 11 — Reservations before the contract (v1.1)

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/11-reservations/intake.md`
- **Branch:** `story/11-reservations`, pull request into **`release/1.1`** (never `main`)
- **Status:** code and tests written 2026-11-28; waiting for CI; not yet tested locally by the
  maintainer

---

## Prerequisites

- `release/1.1` created from `origin/main` at `5008892` (v1.0.1 + the Odoo Apps listing).
- No local Odoo on the current laptop: tests run in GitHub CI (same Docker stack as `make test-ci`).
  Local checks run before every push: `ruff check`, `ruff format --check`, prettier on XML,
  `scripts/check_us_tests.sh`.
- Odoo 19 symbols used were read from `odoo/odoo` branch `19.0` at
  `aa255c890a231708f4b16a467edf9a8235b0020a`: `account.payment.state`
  (draft / in_process / paid / canceled / rejected), `payment_type`, `partner_id`, `amount`;
  `mail.activity.mixin.activity_schedule()`; `AccountTestInvoicingCommon.init_payment()`.

## Story Goal

US-14: a request for an available unit goes to the project's agent, puts the unit on hold once the
agent confirms, becomes reserved when the manager confirms with the reservation amount paid, and
becomes a draft contract. BR-47 to BR-54.

**Prime constraint:** v1 behaviour is unchanged for any unit without a reservation. No v1 test is
edited.

## What changes in v1 files (and why it is safe)

| File | Change | Why v1 is unaffected |
|---|---|---|
| `models/real_estate_unit.py` | `on_hold` selection value; `reservation_ids`; `_compute_state` reads reservations **only after** the live-contract branch | With a live contract the code path is identical; with no reservation `held` is empty and the result is `available`, as before |
| `models/real_estate_contract.py` | `reservation_id` field; `_check_unit_not_held()` called in `create()` / `write()` | It raises only if a held reservation exists for another customer; with none it is a no-op search |
| `models/real_estate_project.py` | `user_id`, `reservation_amount` (new optional fields) | Not read by any v1 code |
| `models/res_company.py`, `res_config_settings.py` | `re_reservation_hold_days` (default 3) + its own constraint | v1 constraint method untouched |
| views, menus, ACL, rules | additions only (contract form shows `reservation_id` only when set) | — |
| `__manifest__.py` | version `19.0.1.1.0`; two new data files | — |

New files: `models/real_estate_reservation.py`, `views/real_estate_reservation_views.xml`,
`data/real_estate_reservation_data.xml` (sequence + its own expiry cron, so the v1 nightly job is not
edited), `tests/test_reservation.py`.

## Steps

1. Spec: US-14, BR-47–BR-54, rights matrix row, §5.4 diagram, Chapter 7 row removed. **Done.**
2. Model `real.estate.reservation`: states and transitions enforced in `write()`; held-unit unique
   index; agent / manager / accountant rights in `write()` and the actions. **Done.**
3. Unit, contract, project, company changes (table above). **Done.**
4. Security (ACL + record rules), views, menu, settings, sequence, cron. **Done.**
5. Tests in `tests/test_reservation.py` (27). **Done.**
5b. Independent review (verification agent): 3 rule gaps through the API and 7 smaller points;
   fixed (state not writable, agent cannot pick the agent, one payment per reservation, contract on
   a held unit only from the reservation, per-record confirm, form readonly rules, to-do closed). **Done.**
6. CI green on `story/11-reservations`: lint + the full suite (107 v1 tests + the new ones), clean
   log. **Pending.**
7. Maintainer installs locally, upgrades a v1.0.1 database to 1.1.0 and walks the flow by hand.
   **Pending (rule 1).**

## Tests

| Test | Covers |
|---|---|
| `test_us_14_request_goes_to_project_agent` | AC-14.1 |
| `test_ac_14_1_request_refused_on_unit_not_available`, `..._several_requests_may_wait` | AC-14.1, BR-49 |
| `test_ac_14_2_agent_confirm_puts_unit_on_hold`, `..._hold_days_is_a_company_setting`, `..._one_held_reservation_per_unit` | AC-14.2, BR-50, BR-53 |
| `test_ac_14_3_agent_sees_only_own`, `..._project_without_agent_goes_to_manager` | AC-14.3, BR-51 |
| `test_ac_14_4_reserve_needs_the_paid_amount`, `..._rights_on_reserve_and_payment`, `..._amount_fixed_once_reserved` | AC-14.4, BR-52 |
| `test_ac_14_5_create_contract_converts`, `..._contract_only_from_reserved` | AC-14.5, BR-54 |
| `test_ac_14_6_held_unit_takes_no_other_contract`, `..._refuses_moving_a_draft_onto_it` | AC-14.6 |
| `test_ac_14_4_manager_cannot_write_the_state`, `..._one_payment_one_reservation`, `test_ac_14_3_agent_cannot_choose_the_agent`, `..._cannot_move_request_to_other_project`, `test_ac_14_1_todo_closed_and_reassigned`, `test_ac_14_2_two_requests_confirmed_together` | review fixes |
| `test_ac_14_7_nightly_job_expires_held`, `..._requests_never_expire` | AC-14.7 |
| `test_ac_14_8_reject_rights`, `..._final_states_do_not_move` | AC-14.8 |
| `test_ac_14_9_unit_without_reservation_as_v1`, `..._converted_reservation_does_not_hold` | AC-14.9 |
| **the 107 v1 tests, unchanged** | AC-14.9 |

## Done Criteria

- [ ] AC-14.1 – AC-14.8 each proven by the tests above, green in CI.
- [ ] AC-14.9: the 107 v1 tests pass with **no change** to any v1 test file
  (`git diff origin/main -- addons/real_estate_eg/tests/` shows only `__init__.py` and the new file).
- [ ] CI log clean (`scripts/check_odoo_log.sh`: no warning or error).
- [ ] Maintainer's local check: upgrade from 1.0.1, walk request → confirm → pay → reserve →
  contract → confirm contract, and the expiry job.
