# 10 — Ship v1.0.0: unit import, demo data, release checks

Plan: [`.squad/plans/installments/10-ship/plan.md`](../../.squad/plans/installments/10-ship/plan.md)

Story 10 turns nine stories of features into something a stranger can install and understand
in two minutes: a unit import for a developer moving to Odoo (US-08), demo data built from
Nile Heights Developments (Chapter 6), checks that every user story has a test, a coverage
number, screenshots and a demo GIF, and the release checklist run by hand.

## What was added

| Piece | Where | Rules |
|---|---|---|
| Unit import wizard, CSV or `.xlsx` | `wizard/real_estate_unit_import.py` | US-08, BR-39 |
| Import dialog, **Configuration → Import Units**, sample file | `wizard/real_estate_unit_import_views.xml`, `static/sample/` | US-08 |
| Demo data: company, users, projects, units, plans, customers | `demo/real_estate_demo.xml` | S10.1, Chapter 6 |
| Demo history: contracts in every state, payments, late fees, cheques | `demo/real_estate_demo.py` | S10.1 |
| `make demo`: fresh database with demo data, log checked | `Makefile`, `scripts/check_odoo_log.sh` | S10.1 |
| Every `US-xx` has a test naming it (pre-commit hook) | `scripts/check_us_tests.sh` | S10.4 |
| `make coverage` | `Makefile`, `.coveragerc` | S10.2 |
| Screenshots and a 60-second GIF | `docs/images/` | S10.2 |

## The import: check everything, then write

BR-39 asks for three things: a file can be imported again without duplicates, a file is
imported **all or nothing**, and every bad row is reported with its row number and reason.

The wizard works in two phases:

1. **Check every row, write nothing.** Each row is read into values and a list of reasons:
   empty code, unknown project, a unit type that is not one of the six, area not above 0,
   negative price, a whole number that is not whole, a number written with a comma, or a code
   already used on an earlier row. All reasons of all rows are collected, not only the first.
2. **Write only if no row is wrong.** Units are looked up by code in the user's current
   company (BR-01 makes the code unique there), archived ones included. A known code is
   updated, and only with the fields that changed, so an unchanged unit is not written at
   all; an archived one is made active again. New codes are created in one `create()`.

If any row is wrong, one `UserError` lists every bad row ("Row 7: unknown project XXX"), and
nothing was written, because phase 2 never ran. The transaction rollback that follows a
`UserError` is a second safety net, not the design.

**Row numbers are spreadsheet rows.** The header is row 1 and the first unit row 2, so the
number in the message is the number the manager sees in Excel. Fully empty rows are skipped
but still counted.

**CSV and Excel give the same rows.** `.csv` is read with Python's `csv` module (UTF-8; the
`utf-8-sig` codec also accepts the byte order mark Excel writes). `.xlsx` is read with
`openpyxl`, already in Odoo's requirements, with `data_only=True` so a formula is read as its
last saved value, as Odoo's own `base_import` does. After that, both are the same list of
`(row number, cells)`, and every check is written once. Excel gives `302.0` for `302`, so
whole floats lose their `.0` before they are read as text.

**A comma in a number is an error, not a guess.** `8,580,000` is a thousands separator in
Egypt; `8,5` is a decimal comma elsewhere. The wizard refuses both and says so.

**A changed price never reaches a signed contract.** The contract's `price` is computed from
its unit only and stored (BR-08), so a re-imported list price updates the unit and leaves
every contract alone. T2 checks it.

**Rights.** Only the sales manager can open the wizard (its access rule), and the writes run
as that user, with the unit's own rights and rules, never `sudo()`.

### Why not Odoo's standard import?

Odoo's **Import records** (`base_import`) can create units from a spreadsheet and reports
problems with their rows. But it matches existing records only by external ID or database ID,
not by unit code, so a second import of the developer's own sheet would create every unit
again unless the sheet carried Odoo's IDs. BR-39's own checks (a code repeated in the file, a
number written with a comma) are not its rules either. A small wizard keyed on the unit code
was the simpler fit.

## Demo data: replaying history

Demo data must show every screen with something on it: contracts in every state, overdue
lines, an at-risk contract, late fees and cheques. Typed-in XML cannot do that, because those
come from invoices, payments and the nightly job. So the demo has two parts, the same pattern
as Odoo's own `account/demo/account_demo.py`:

1. **`demo/real_estate_demo.xml`** holds what is static: the company (Egypt, EGP, the §6.4
   policy), the five people as users in their groups (login = first name, password `demo`),
   three projects, 24 units of every §6.2 type, the five plans and fictional customers.
2. **A `<function>` tag** at the end calls `real.estate.contract._demo_load()`, which replays
   about fifteen months of history with dates counted back from the install day.

The replay uses the module's own methods that take the day as a parameter:
`_invoice_due_lines(day)` invoices each line on its due date, the accountant (Tarek)
registers payments with a payment date, and `_cron_nightly(today)` computes the late fees
from that payment history. Only confirmation is replayed by hand (`_demo_confirm()`: the same
checks, the state and its date, and the invoices due that day), because `action_confirm()`
always uses today. Because the dates count back from the install day, the overdue and
at-risk lists are never empty, whenever the demo is installed.

| Contract | State | Shows |
|---|---|---|
| Ahmed, HNC-B07-0401 | draft | A schedule waiting for the manager |
| Mona, HNC-B07-0302 (Example A's unit) | confirmed | Every line paid on time; a cleared cheque and two held ones |
| Youssef, PSS-B01-0101 | confirmed, **at risk** | Installment 1 paid 20 days late, installment 2 unpaid ~70 days; late fees billed by Hoda; a bounced cheque and its replacement in To Deposit |
| Delta (a company), CBP-A02-0105 | confirmed | Installment 4 overdue 15 days with a deposited cheque: still overdue (BR-42) |
| Laila, HNC-B08-1201 | delivered | The maintenance deposit invoiced on delivery |
| James (foreign, passport), PSS-B05-0001 | closed | A cash plan, paid, delivered, closed by the nightly job (BR-12) |
| Sherif, HNC-B08-0101 | cancelled | 15% retention on what was paid (BR-33) |
| Nadia, PSS-B01-0102 | confirmed today | Only the down payment invoiced |

**A company of its own.** Odoo's demo company ("YourCompany") is in USD with posted entries,
so it cannot become an EGP company. Nile Heights is a new company. A new company gets no
chart of accounts by itself, so the loader loads Odoo's generic chart, then sets the fiscal
country to Egypt and the currency to EGP (the generic chart says US and USD, and nothing is
posted yet). A real Egyptian company would install `l10n_eg` instead
([ADR in Story 04](04-accounting-link.md#adr-l10n_eg-is-not-a-dependency)).

**Tests never use it.** `make test` installs without demo data (`with_demo = False`), and the
tests build their own company. To prove they also do not collide with it, the whole suite was
run on a database with demo data loaded: 106 tests, 0 failed.

## Every user story has a test

S10.4 asks that every `US-xx` has at least one test naming it. Four did not: US-02, US-03 and
US-12 had tests (`AC-02.x`, `AC-03.x`, `AC-12.x`) whose names and docstrings did not say the
story; US-08 is new. The three are now named in the docstrings of tests that already prove
them; no test was renamed.

`scripts/check_us_tests.sh` reads every `#### US-xx` heading of the business document and
fails if no file under `tests/` names it. It runs as a local pre-commit hook, so a new story
without a test fails `make lint` and CI.

## Coverage

`make coverage` runs the same tests as `make test` under `coverage.py`. It measures the
module without its tests, the demo loader (run by `make demo`, never by the tests) and the
manifest (read by Odoo as data). Result: **97 %** of 990 statements. It is local only; CI is
unchanged.

## Release checklist (S10.3)

Run on 2026-11-25 on a fresh `make demo` database (a copy, so the demo stayed clean), in the
browser as the demo users and in `make shell`. Every item passed.

| # | Check | Result |
|---|---|---|
| 1 | Fresh database, install with demo data: no error, no warning | Pass: `make demo`, `check_odoo_log: OK` |
| 2 | Contract for a Horizon unit, 10 % / 8 years quarterly, confirmed | Pass: Salma created NH/2026/00007 on HNC-B07-0402 and generated `NH-STD-8Q`; Omar confirmed it; the down payment was invoiced at once |
| 3 | Schedule sums exactly to the price, maintenance deposit separate | Pass: 33 lines sum to 8,580,000; the last installment is 241,297; the deposit is 686,400, due at delivery |
| 4 | Nightly job twice: nothing double-charges | Pass: 53 journal entries and 6,542.50 EGP of accrued fees before, after the first and after the second run |
| 5 | The demo agent cannot see the other agent's contracts | Pass: Salma sees her 4 contracts, none of Karim's 4 |
| 6 | Print the Arabic contract PDF and read it | Pass |
| 7 | Re-run the unit import: counts unchanged | Pass: the 24 demo units exported and imported twice: 24 units, 0 created, 24 unchanged each time |
| 8 | Full suite green; every `US-xx` named by a test | Pass: 106 tests; `check_us_tests: OK - all 13 user stories` |
| AC-04.4 | At-risk contracts in one click | Pass: Collections → At-Risk Contracts lists the one at-risk contract |
| AC-07.1 | Arabic letters joined, Arabic and English side by side | Pass (read on the rendered PDF) |
| AC-07.2 | A 60-character customer name, layout intact | Pass: the name wraps on two lines in both columns; the table keeps its width |
| M1 | Import dialog | Pass: the dialog opens for the manager; a file with an unknown project gives "Row 3: unknown project XXX" and imports nothing |

One small finding, not fixed in v1: the plan picker searches plan **names**, not codes, so
typing `NH-STD-8Q` finds nothing; "Standard" does.

## Screenshots and the GIF

Every image in the README was taken from a fresh `make demo` database in the browser, as the
demo users. The GIF is a 60-second click-through built from those real screenshots with
`ffmpeg`, one caption per screen; it is not a screen recording.

## Tests

`tests/test_unit_import.py`, every import run as the manager or a non-manager user, never as
admin; files are built in the test (CSV with `csv`, `.xlsx` with `openpyxl`).

| # | Test | Proves |
|---|---|---|
| T1 | 200 rows create 200 units with the file's values, from CSV and from `.xlsx`; the dialog's button shows the counts | AC-08.1 |
| T2 | The same file again: 0 created, 201 unchanged; a new price updates that unit only; its contract keeps its price | AC-08.2, BR-08 |
| T3 | Row 7 names project `XXX`: the error says "Row 7: unknown project XXX", nothing is created or changed; same from `.xlsx` | AC-08.3 |
| T4 | Bad type, area 0, negative price, code twice, a half bedroom, a comma, an empty code: every row in one error; empty rows counted | BR-39 |
| T5 | Bad files: missing or unknown column, semicolons, no data, not UTF-8, a broken `.xlsx`, `.xls`, `.txt` | BR-39 |
| T6 | An archived unit is updated and reactivated, not duplicated | BR-39 |
| T7 | The sample file in the dialog imports cleanly | US-08 |
| T8 | Agents, collections and the accountant cannot import; codes match in the user's company only | BR-35, BR-01 |

106 tests pass (98 before this story), with a clean log, locally and in the CI image.

**Negative checks** (each seen failing, then undone before `git add`):

| # | Change | Result |
|---|---|---|
| N1 | Write the good rows before reporting the errors | T3 and T4 fail: the good rows were created |
| N2 | Match units by code without the company (`sudo()`) | T8 fails: company 2's unit is matched |
| N3 | Remove `US-12` from the test docstrings | `check_us_tests.sh` fails: "no test names US-12" |
| N4 | A demo record with an unknown field | `make demo` fails |

**Testing trap 1: `assertRaises` hides partial writes.** N1 first did **not** fail. Odoo's
`assertRaises` (`_assertRaises()` in `odoo/tests/common.py`) opens a savepoint and rolls it
back when the exception comes, so rows written before the error vanish before the test looks.
The all-or-nothing tests catch the error with a plain `try/except` instead, so a partial
write would stay visible. Then N1 failed as it should.

**Testing trap 2: Odoo swallows demo errors.** When demo data fails, Odoo rolls it back,
installs the module without it and logs one `WARNING` ("demo data failed to install"). The
install itself succeeds. Only the log check catches it, which is why `make demo` runs
`check_odoo_log.sh`.

## Alternatives considered

- **Odoo's standard import** — see above: it does not match by unit code.
- **Write each row and roll back on error.** It works because of the transaction, but the
  manager would still get only the first error, and a bug that commits early would leave half
  a file behind. Checking first gives every error at once and writes nothing by design.
- **Demo data in XML only.** It cannot create invoices, payments or late fees that match;
  hand-written journal entries would not match what the module itself would post.
- **Demo on Odoo's own demo company.** It is in USD with posted entries; Nile Heights is EGP.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-10--ship-v100).

1. The import checks every row before writing anything. A `UserError` rolls the transaction
   back anyway, so why check first? Give two reasons, one about the manager and one about
   the tests.
2. Importing the same file twice creates no duplicates. What makes a row "the same unit",
   and why is that search limited to the current company?
3. Why does the demo replay history with the module's own methods (`_invoice_due_lines(day)`,
   `_cron_nightly(day)`) instead of writing invoices and late fees straight into the
   database?
