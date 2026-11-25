# 10 — Ship v1.0.0: unit import, demo data, README

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/10-ship/intake.md`
- **Branch:** `story/10-ship`
- **Status:** Done Criteria approved 2026-11-25; Steps 0–8 done (106 tests green, coverage 97 %,
  checklist passed); in review. Step 9 (tag) after merge, with the maintainer's OK

---

## Prerequisites

- Stories 01–09 merged; `main` at `e442bdc`; CI green on `main`; `make test` gives 0 failed of 98
  tests with a clean log; `make lint` passes.
- Local `main` clean and in sync with `origin/main`.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- `coverage==7.17.4` is already in `requirements-dev.txt` and in `venv/`. `ffmpeg` is installed
  (GIF conversion). No Chrome/Chromium and no Playwright on this machine, so screenshots and the
  GIF may need the maintainer's hands (Step 6).
- Port 8097 is held by another process: tests use free ports, e.g.
  `make test ARGS="--http-port 8187 --gevent-port 8188"`.

## Story Goal

Make `real_estate_eg` something a stranger can install and understand in two minutes, and ship it as
`v1.0.0`.

1. **Unit import** — CSV or Excel `.xlsx` ([US-08](../../../../docs/business-requirements.md#us-08--import-units-from-a-spreadsheet "US-08: As an administrator, I want to import units from a spreadsheet, so that a developer moving to Odoo does not retype hundreds of records."), [BR-39](../../../../docs/business-requirements.md#collections-documents-and-data "BR-39: Importing units from a spreadsheet is repeatable: importing the same file again updates the existing units, matched by unit code, and creates no duplicates. A file is imported all or nothing: if any row is wrong, nothing is imported and every bad row is reported with its row number and reason.")): a manager uploads a CSV or `.xlsx` file of units. Units are matched
   by code inside the company: new codes are created, known codes are updated, nothing is
   duplicated. Every row is checked first; if any row is wrong, nothing is written and the error
   lists every bad row with its row number and reason.
2. **Demo data** from Chapter 6 (S10.1): Nile Heights' three projects, units and prices, the five
   plan templates, the collection policy, the five people as users in their groups, generated
   customers, contracts in every state, and a few cheques. A fresh install with demo data logs no
   error and no warning. Tests never rely on it.
3. **README** (S10.2): screenshots, a 60-second demo GIF, the design-notes index (01–10), test count
   and coverage, demo logins, and "possible next" from Chapter 7.
4. **Release checks** (S10.3, S10.4): the project plan's end-to-end checklist, the manual checks
   AC-04.4, AC-07.1, AC-07.2, and a check that every `US-01`…`US-13` has a test naming it.
5. **Release** (S10.5): `CHANGELOG.md` `1.0.0`, then the `v1.0.0` tag after merge, with the
   maintainer's OK.

Not in this story: importing existing contracts (Chapter 7), a hosted demo, and anything for the
Odoo Apps Store (listing files and publishing are left for later, by the maintainer's decision).

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/10-ship/intake.md` — US-08, BR-39, AC-08.1–08.3, S10.1–S10.5, Ch.6
  reference data.
- `docs/business-requirements.md` — §1.3 US-01…US-13 (the list S10.4 checks), §1.4 story map, §6
  (all demo numbers and people), §6.6 worked examples, §7 "Beyond v1" (the "possible next" list;
  ETA row names `l10n_eg_edi_eta`; revenue recognition at delivery is beyond v1, BR-43).
- `docs/project-plan.md` — "End to end, before tagging v1.0.0" (8 items), "Explicitly not in v1",
  "Target layout" (`demo/`, `static/description/`, `CHANGELOG.md`).
- `README.md` — stale status line ("Story 03 of 10"), "What v1 will do", roadmap rows 09 ("in
  review") and 10, "How this is built" (the AI disclosure, kept as agreed).
- `addons/real_estate_eg/__manifest__.py` — already has `version` `19.0.1.0.0`, `license` `LGPL-3`,
  `author`, `website`, `summary`; no `demo` and no `images` key yet.
- `addons/real_estate_eg/README.rst` — still says "Status: skeleton".
- `addons/real_estate_eg/models/real_estate_unit.py` — `code`, `project_id`, `unit_type` (selection
  keys `apartment`, `duplex`, `chalet`, `twin_house`, `office`, `retail`), `bedrooms`, `area`,
  `floor`, `list_price`; `_code_company_unique` (`UNIQUE (company_id, code)`), `_area_positive`,
  `_list_price_not_negative`; `company_id` related to the project's company.
- `addons/real_estate_eg/models/real_estate_project.py` — `code` unique per company.
- `addons/real_estate_eg/models/real_estate_contract.py` — `price` is computed from `unit_id` only
  and stored (BR-08), so a re-imported list price never changes a signed contract;
  `_generate_schedule(plan)`, `action_confirm()`, `action_deliver()`, `_cancel_with_reason()` (via
  the cancel wizard's `action_confirm_cancel()`), `_cron_nightly(today=None)`.
- `addons/real_estate_eg/models/res_company.py` — `re_advance_account_id`,
  `re_maintenance_account_id`, `re_late_fee_account_id` (liability / income types), and the §6.4
  settings with their defaults.
- `addons/real_estate_eg/security/security.xml`, `ir.model.access.csv` — the three groups; units are
  written by the manager only, so the import is a manager action.
- `addons/real_estate_eg/views/real_estate_menus.xml` — `real_estate_config_menu` (manager only),
  `real_estate_unit_menu`.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon` and its non-admin users.
- `addons/real_estate_eg/tests/` — names in use: US-01, US-04–07, US-09–11, US-13 appear;
  **US-02, US-03, US-08 and US-12 appear in no test file yet** (AC-02.x / AC-03.x / AC-12.x do).
- `Makefile` (`test`, `test-ci`, `lint`), `scripts/check_odoo_log.sh`, `odoo.conf.example`
  (`with_demo = False`, so `make test` never loads demo data), `.pre-commit-config.yaml`,
  `.github/workflows/ci.yml`.
- `docs/design-notes/01…09`, `docs/learning-log.md`, `docs/images/` (two Story 08 PDF images).

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/odoo/tools/config.py` — `--with-demo` / `--without-demo` options (demo is off by
  default).
- `odoo-src/odoo/odoo/tools/convert.py` — `_tag_function` / `_eval_xml`: a `<function>` tag may call
  a model method, including one starting with `_` (only `__` names are refused); the eval context has
  `DateTime`, `relativedelta`, `ref`, `Command`.
- `odoo-src/odoo/addons/account/__manifest__.py` (`'demo'` key) and `addons/account/demo/` — the
  pattern of a Python `demo/` package (`account_demo.py`) whose methods are called from demo XML;
  `account_demo.xml` loads `generic_coa` for a company with no country when demo is installed.
- `odoo-src/odoo/addons/account/models/ir_module.py` — a chart template is auto-loaded on the
  current company when `account` is installed; Step 3 checks a chart and a bank journal exist before
  demo contracts are confirmed.
- `odoo-src/odoo/addons/account/models/account_account.py` — `company_ids` (Many2many).
- `odoo-src/odoo/addons/account/models/account_payment_method.py` — `payment_account_id` on the
  payment method line (the Outstanding Receipts setting).
- `odoo-src/odoo/addons/account/wizard/account_payment_register.py` — `action_create_payments()`
  (demo payments, as in the tests).
- `odoo-src/odoo/odoo/addons/base/models/res_users.py` — `group_ids` (Odoo 19 name);
  `odoo/addons/base/data/res_users_demo.xml` — demo users carry a `password` field.
- `odoo-src/odoo/addons/base_import/models/base_import.py` — `_read_file()`, `_read_csv()`: the
  standard import, considered and not used (see Edge Case 11); `_read_xlsx()` reads Excel with
  `openpyxl.load_workbook(io.BytesIO(...), data_only=True)` — the same call our wizard uses.
- `odoo-src/odoo/requirements.txt` — `openpyxl==3.1.2` for Python ≥ 3.12 (installed in `venv/` and in
  the Odoo image), so `.xlsx` support adds no dependency.

## Implementation tasks

Small steps, in order, **one commit per step**, each ending with a Key points block (built + ids,
Odoo concept, trap, one-line takeaway). Files are new unless marked *(edit)*; module paths are under
`addons/real_estate_eg/`.

**Step 0 — Branch and plan.** `git switch -c story/10-ship` from up-to-date `main`. Commit this
plan and `00-overview.md` *(edit)* (row 10: file written). `README.md` *(edit)*: roadmap 09 → done,
10 → in progress. Local only: `plan.ar.md`, `00-overview.ar.md`.

**Step 1 — Import wizard, logic and tests** (`wizard/real_estate_unit_import.py`,
`wizard/__init__.py` *(edit)*, `security/ir.model.access.csv` *(edit)*,
`tests/test_unit_import.py`, `tests/__init__.py` *(edit)*). *US-08, BR-39, AC-08.1–08.3.*
1. `real.estate.unit.import` (`TransientModel`): `file` (Binary), `filename`. The extension picks
   the reader: `.csv` (UTF-8, comma) or `.xlsx` (first sheet, `openpyxl`, `data_only=True` so
   formulas give their values). Both readers return the same list of rows, so every check below is
   written once.
2. Columns (header row): `code`, `project_code`, `unit_type`, `bedrooms`, `area`,
   `floor`, `list_price`. Rows are numbered as in a spreadsheet: header = row 1, first unit = row 2.
3. **Phase 1 — check every row, write nothing.** Per row: code present; code not repeated in the
   file; project code known in the user's current company; `unit_type` one of the selection keys;
   `area` > 0; `list_price` ≥ 0; numbers parse. Every problem is collected as
   `Row N: <reason>`; missing or unknown header columns are one file-level error.
4. **Phase 2 — only if there are no errors.** Units are looked up by code in the current company
   (BR-01 key), including archived ones; known → `write()` only changed fields; new → one
   `create()` for all of them. Returns a notification "N created, M updated, K unchanged".
5. Any error → one `UserError` listing every bad row; nothing is written (it is raised before
   phase 2; the request's transaction would roll back anyway).
6. Access: manager only (ACL on the wizard); units' own ACL and rules still apply to the writes,
   so no `sudo()`.
7. Tests T1–T5 first. *Check:* `make test`.

**Step 2 — Import screen** (`wizard/real_estate_unit_import_views.xml`,
`views/real_estate_menus.xml` *(edit)*, `__manifest__.py` *(edit)*,
`static/sample/real_estate_units_sample.csv`). Dialog with the file field, the column list and a
link to the sample file; menu **Configuration → Import Units** (manager). *Check:* M1 on `re_dev`.

**Step 3 — Demo data** (`demo/real_estate_demo.xml`, `demo/real_estate_demo.py`, `demo/__init__.py`,
`__init__.py` *(edit)*, `__manifest__.py` *(edit)*: `demo` key, `Makefile` *(edit)*). *S10.1.*
1. XML records (noupdate): the three projects (§6.1), units of every type in §6.2 with Chapter 6
   codes and prices (about 24, a few per type), the five plan templates (§6.3), the company's §6.4
   settings and its three accounts (created for the demo company), the five users (§6.5) in their
   groups (Omar → manager; Salma, Karim → agent; Hoda → collections; Tarek →
   `account.group_account_invoice`), login = first name, password `demo` (as Odoo's own demo users),
   and generated customers with obviously fictional names and national IDs.
2. A `<function>` call to `real.estate.contract._demo_load_contracts()` (Python in `demo/`, the
   account pattern) creates, with dates relative to today: draft; confirmed and on time; confirmed
   with overdue lines and one at risk (> 60 days); delivered; closed (cash plan, paid, delivered,
   closed by the nightly job); cancelled after payments (retention computed). Payments go through
   `account.payment.register`, the nightly job through `_cron_nightly()`. It also records cheques:
   held (one dated before today, so To Deposit is not empty), deposited, cleared, and a bounced one
   with its replacement.
3. Before confirming anything it checks the company has a chart, a sales journal and a bank journal
   with Outstanding Receipts set, and sets what the demo needs (the README's "Accounting setup").
4. `Makefile`: `make demo` — drop `re_demo`, install the module `--with-demo`, run
   `scripts/check_odoo_log.sh` on its log. *Check:* `make demo` clean; `make test` still 0 failed.

**Step 4 — Every US has a test** (`scripts/check_us_tests.sh`, `.pre-commit-config.yaml` *(edit)*,
test docstrings *(edit)* in `tests/test_schedule.py`, `tests/test_invoicing.py`,
`tests/test_payment_state.py`, `tests/test_delivery_closing.py`). *S10.4.*
1. Add the missing `US-02`, `US-03`, `US-12` to the docstrings of tests that already prove them
   (`test_ac_02_1_generate_from_wizard`, `test_ac_03_1_invoice_at_confirmation`,
   `test_ac_12_1_close_when_paid`); US-08 comes from Step 1. Names in docstrings only — no test is
   renamed.
2. The script reads every `#### US-xx` heading of `docs/business-requirements.md` and fails if any
   id is missing from `addons/real_estate_eg/tests/`. A local pre-commit hook runs it, so `make lint`
   and CI run it too.
3. N3 below. *Check:* `make lint`.

**Step 5 — Coverage** (`Makefile` *(edit)*: `make coverage`, `.coveragerc`). `coverage run` around
the same Odoo test command, `--source` the module, tests omitted; `coverage report` prints the
percentage. Local only (CI unchanged). *Check:* number recorded for the README.

**Step 6 — Screenshots and the GIF** (`docs/images/*.png`, `docs/images/demo.gif`). From a running
`re_demo` database: contract form with schedule, Overdue list, aging pivot, To Deposit, import
dialog with a row error, PDF page. If no tool here can save browser screenshots or record the
screen, the maintainer gets exact steps (pages, order, ≤ 60 s, `ffmpeg` command to make the GIF)
and the README holds a clearly marked placeholder until the real files arrive. Nothing is faked.

**Step 7 — End-to-end checklist** (S10.3) on `re_demo`, each result written down honestly in the
design note: the 8 items of `docs/project-plan.md`, plus AC-04.4 (at-risk filter in one click),
AC-07.1 (Arabic joined, columns side by side in the PDF), AC-07.2 (60-character name, layout intact).
Item 7 imports a CSV of the demo units twice and compares counts.

**Step 8 — Docs + PR.** `README.md` *(edit)*: status v1.0.0, "What v1 does", screenshots + GIF,
demo logins (`make demo`), design-notes index 01–10, test count and coverage, "Possible next" from
Chapter 7 (ETA as `l10n_eg_edi_eta`; revenue recognition at delivery listed as v1.1, not as done),
AI disclosure unchanged, roadmap 09 and 10 → done. `CHANGELOG.md` with `1.0.0`
(Keep a Changelog format, one line per story). `docs/design-notes/10-ship.md` (import design,
all-or-nothing, demo pattern, US trace check, checklist results; 3 explain-back
questions). `addons/real_estate_eg/README.rst` *(edit)*: real status instead of "skeleton". `docs/learning-log.md` *(edit)*: Story 10 placeholder. Done Criteria ticked in
`plan.md` and `plan.ar.md`. PR; CI green; the maintainer answers in `docs/learning-log.md` and
merges with "Create a merge commit".

**Step 9 — Release (only with the maintainer's OK).** After merge and green CI on `main`:
`git tag -a v1.0.0` on the merge commit and push the tag. Ask before creating a GitHub Release.
Then the private learning guides (local, gitignored).

## Edge Cases & Failure Modes

1. **Same file twice** (AC-08.2): second run creates 0 and updates only changed fields; "unchanged"
   counted, no write → no needless `write_date` change.
2. **Price change on a sold unit:** the unit's list price changes; the contract keeps its frozen
   `price` (BR-08). Stated in the design note.
3. **Unknown project** (AC-08.3): row reported, nothing written — also when the other 199 rows are
   fine.
4. **Several bad rows:** all reported in one message, not only the first.
5. **Code twice in one file:** an error for the second row ("code already on row N").
6. **Archived unit with that code:** found and updated, not duplicated (the DB constraint would
   refuse a duplicate anyway).
7. **Other company:** project and unit codes are looked up in the current company only; a unit with
   the same code in another company is a different unit (BR-01 is per company).
8. **Bad file:** empty file, missing column, non-UTF-8 CSV, a `;` separated CSV, an old `.xls` or a
   broken `.xlsx`, any other extension → one clear file-level error, no traceback.
8b. **Excel specifics:** numbers arrive as numbers (no thousands-separator problem); formulas are
   read as their last saved values; fully empty rows are skipped but still counted, so row numbers
   match what the manager sees in Excel; only the first sheet is read.
9. **Extra spaces / thousands separators** in numbers (`8,580,000`): spaces stripped; a comma in a
   number is reported as an error, not guessed.
10. **Non-manager:** agent, collections and accountant cannot open the wizard or write units
    (`AccessError`).
11. **Why not Odoo's standard import** (`base_import`): it updates existing records by external
    or database ID only, not by unit code, so re-importing the developer's sheet would duplicate
    every unit (BR-39). Recorded in the design note.
12. **Demo and tests:** `make test` runs without demo (`with_demo = False`); the test company is
    Odoo's test company, not the demo one, so demo codes cannot clash. T7 proves the suite also passes
    on a database that has demo data.
13. **Demo chart:** if no chart or bank journal exists when the demo loads, confirming would fail;
    the loader checks and sets what it needs, or fails with a clear message (never a log warning).
14. **Demo dates:** relative to today, so overdue and at-risk lists stay filled whenever installed.
15. **Demo passwords:** `demo`, as Odoo's own demo users; documented as local-only, never for a real
    database.
16. **README honesty:** nothing claimed that v1 does not do; placeholders marked.

## Test Plan

Tests in `addons/real_estate_eg/tests/test_unit_import.py`, `@tagged("post_install",
"-at_install")`, on `RealEstateCommon`. Every action runs `with_user(...)` as a non-admin user;
nothing relies on demo data. CSV files are built in the test.

| # | Test | Proves |
|---|---|---|
| T1 | `test_ac_08_1_import_200_units` — US-08: the manager imports a generated 200-row file over two projects; 200 units exist with the file's values. Once as CSV, once as `.xlsx` (built with `openpyxl` in the test) | AC-08.1, BR-39 |
| T2 | `test_ac_08_2_reimport_updates` — the same file again: still 200 units, 0 created; one row with a new price updates that unit only; a contract on that unit keeps its price | AC-08.2, BR-39, BR-08 |
| T3 | `test_ac_08_3_unknown_project_nothing_imported` — 10 rows, row 7 names project `XXX`: `UserError` naming "Row 7" and the unknown project; no unit created, no existing unit changed; the same with an `.xlsx` file gives the same row number | AC-08.3, BR-39 |
| T4 | `test_import_row_errors` — bad type, area 0, negative price, code twice, missing column: every bad row reported with its number in one error; nothing written. An `.xls` / `.txt` file is refused with a clear message | BR-39 |
| T5 | `test_import_rights` — agent, collections officer and accountant get `AccessError`; units in another company are not matched | BR-35, BR-01 |
| T6 | `make demo` — fresh `re_demo` with demo: install succeeds, log has no `WARNING`/`ERROR`/`CRITICAL`; contracts exist in all six states; cheques in all four states | S10.1 |
| T7 | `make test` (98 + new tests, 0 failed); the same suite on a database with demo data loaded (`make test ARGS="--with-demo …"`) | S10.1, tests never rely on demo |
| T8 | `scripts/check_us_tests.sh` (in `make lint` and CI) | S10.4 |
| T9 | `make lint`, `make test-ci`, CI on the PR and on `main` | S10.4 |
| M1 | *(manual)* Import dialog on `re_dev`: sample file, then a file with an error | US-08 |
| M2 | *(manual, Step 7)* project-plan checklist items 1–8, AC-04.4, AC-07.1, AC-07.2 | S10.3 |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: write each valid row as it is checked (no phase split) → T3 fails (rows 1–6 created).
- N2: match units by code without the company → T5 fails.
- N3: remove `US-12` from the test docstrings → `check_us_tests.sh` fails.
- N4: add a demo record that logs a warning (e.g. an unknown field) → `make demo` fails.

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/10-ship
make test ARGS="--http-port 8187 --gevent-port 8188"                 # 0 failed, log clean
make test ARGS="--with-demo --http-port 8187 --gevent-port 8188"     # same, with demo loaded
make demo ARGS="--http-port 8187 --gevent-port 8188"                 # fresh install with demo, log clean
make coverage ARGS="--http-port 8187 --gevent-port 8188"             # percentage for the README
make lint                                                            # includes the US trace check
make test-ci                                                         # CI Docker stack
make run DB=re_demo ARGS="--http-port 8187 --gevent-port 8188"       # Steps 6–7 in the browser
gh pr checks                                                         # green on the PR
gh run list --branch main --limit 1                                  # green after merge
git tag -a v1.0.0 -m "v1.0.0" && git push origin v1.0.0              # only with the maintainer's OK
```

## Done Criteria

- [x] **AC-08.1** Given a file of 200 units, importing it creates 200 units. *Proof:* T1 (CSV and
  `.xlsx`).
- [x] **AC-08.2** Importing the same file again creates nothing new; a changed price in the file
  updates the existing unit. *Proof:* T2.
- [x] **AC-08.3** Given a file where one row names an unknown project, nothing is imported and the
  error gives that row's number and reason. *Proof:* T3 (T4 for other bad rows).
- [x] **S10.1** Installing `real_estate_eg` with demo data on a fresh database gives no error and no
  warning in the log; demo data has the three projects, unit types and prices, the five plan
  templates, the collection policy, the five people as users in their groups, and contracts in every
  state. *Proof:* T6, T7.
- [x] **S10.2** README has screenshots, a 60-second demo GIF, the design-notes index, test count and
  coverage, and the "possible next" list from Chapter 7 (ETA named `l10n_eg_edi_eta`). *Proof:*
  README review, Step 6, Step 8.
- [x] **S10.3** The project plan's end-to-end checklist passes, including the manual checks AC-04.4,
  AC-07.1 and AC-07.2. *Proof:* M2, results in the design note.
- [x] **S10.4** Every `US-xx` has at least one test naming it; the suite is green in CI. *Proof:* T8,
  T9.
- [ ] **S10.5** `CHANGELOG.md` has the `1.0.0` entry and the `v1.0.0` tag is pushed. *Proof:* Step 8,
  Step 9. *(CHANGELOG done; the tag waits for the merge and the maintainer's OK.)*
