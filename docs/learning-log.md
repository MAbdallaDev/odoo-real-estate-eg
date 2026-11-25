# Learning log

Two records kept side by side:

1. **Explain-back answers** — each story's design note ends with three questions; the
   maintainer answers them here, in their own words, before the next story starts.
2. **Mistakes caught** — every time the AI assistant got something wrong and review, a
   test or a quality gate caught it. This is the evidence that the code is reviewed, not
   just generated.

---

## Explain-back answers

### Story 01 — Environment and module skeleton

Questions: [`design-notes/01-environment.md`](design-notes/01-environment.md#explain-back-questions)

1. Without dropping `re_test`, the old database stays: the module is already installed, so
   `-i` acts as an update, not a fresh install, and old data stays. A test could then pass or
   fail because of leftover data, and an error that only happens on a fresh install would be
   missed. Without `--test-tags /real_estate_eg`, Odoo would also run the tests of every module
   installed with ours (`account`, `mail` and their dependencies), so the run would take tens
   of minutes instead of seconds.
2. First, a warning or error in the log: Odoo still exits 0, like the missing `http_interface`
   warning on our first run. Second, zero tests ran: if `tests/__init__.py` does not import the
   test file, Odoo finds no test and still exits 0 (negative check N2).
   `scripts/check_odoo_log.sh` catches both: it fails on any `WARNING`/`ERROR`/`CRITICAL` line
   and when no `real_estate_eg` test ran.
3. From Docker images: `docker/docker-compose.ci.yml` starts two containers from ready-made
   images, `postgres:16` and the official `odoo:19.0`, and mounts our `addons/` folder into the
   Odoo container, so nothing has to be installed on the CI machine. The images are pinned by
   digest so the version never changes by itself: the `odoo:19.0` tag moves to new builds, so
   without the pin CI could fail one day with no change in our code. We update the digest on
   purpose, in a commit.

### Story 02 — Core models, views, states and access rights

Questions: [`design-notes/02-core-models.md`](design-notes/02-core-models.md#explain-back-questions)

1. The Python check runs before the database constraint and gives a better message: it shows
   the existing contract's reference, while the database constraint does not. The database
   constraint is the guard: when two users save a contract for the same unit at the same
   moment, each Python check cannot see the other user's contract, because it is not saved
   yet, so both pass. Only the unique index in Postgres sees both and refuses the second one.
   The Python check uses `sudo()` because, from Story 06, an agent cannot see another agent's
   contract, but the unit is still taken.
2. The type of `list_price` is not the cause; the dependency is. With
   `@api.depends("unit_id.list_price")`, Odoo recomputes `price` on every contract of the
   unit when its list price changes, confirmed contracts included, so a price the customer
   already signed would change. AC-01.2 proves the choice: a later list price change does
   not reach an existing contract. AC-01.6 proves the other side: changing the unit on a
   draft takes the new unit's price.
3. An agent cannot confirm because of Python: `action_confirm()` calls `_check_manager()`,
   which raises an `AccessError`; the button's `groups=` only hides it. A collections
   officer cannot edit because of the access rights in `ir.model.access.csv`: read only, no
   write, create or delete. An agent still sees other agents' contracts because there are no
   record rules yet: the access rights give read on the whole table, so every row is
   visible. Story 06 adds record rules (`ir.rule`): an agent sees only their own contracts,
   and a user sees only their own company's records.

### Story 03 — Payment plan templates and the schedule generator

Questions: [`design-notes/03-schedule-generator.md`](design-notes/03-schedule-generator.md#explain-back-questions)

1. `round()` rounds a .5 to the even number: `round(858000.5)` gives 858,000, but the rule
   wants 858,001. A float cannot store some decimals exactly: `1310730 * 0.35` is
   `458755.49999999994`, so it rounds to 458,755 instead of 458,756. `Decimal` keeps the exact
   digits and `ROUND_HALF_UP` always rounds .5 up. The last installment makes the schedule sum
   exactly to the price because it is not rounded: it is the rest (price − down payment) minus
   the other installments, `rest − installment × (N − 1)`.
2. If we chain from the previous due date, a short month changes the day for all the next
   installments. 31 Jan 2027 + 1 month gives 28 Feb 2027, because February has no 31st, so
   we use the last day of the month. Chaining from 28 Feb gives 28 Mar, 28 Apr, 28 May: the
   wrong day for every month after February. From the contract date, each installment is
   31 Jan + k months, so we get 31 Mar, 30 Apr, 31 May.
3. `@api.constrains` runs after the INSERT. The unique index refused the INSERT first, so the
   Python check never ran and the user saw a database error without the contact's name. Now
   the check runs before `super().create()`. The unique index still catches two customers
   created at the same time, which the Python check cannot see. `sudo()` lets the search see
   contacts of other companies, and `active_test=False` makes it find archived contacts too.

### Story 04 — Accounting link: invoices, payment state, closing and cancellation money

Questions: [`design-notes/04-accounting-link.md`](design-notes/04-accounting-link.md#explain-back-questions)

### Story 08 — Bilingual Arabic / English contract PDF

Questions: [`design-notes/08-bilingual-pdf.md`](design-notes/08-bilingual-pdf.md#explain-back-questions)

*Drafted by the AI at the maintainer's request.*

1. Odoo's translation system prints a report in one language: the user's or the partner's. An
   Egyptian contract needs both languages on the same page, so the Arabic words are fixed
   labels in a right-hand column marked `dir="rtl"`. Inside a right-to-left paragraph, the bidi
   algorithm reorders Latin text and numbers: without `<span dir="ltr">`, `8,580,000 EGP` would
   show as `EGP 8,580,000`. The span keeps its order.
2. The official `odoo:19.0` image has no Arabic font, so wkhtmltopdf would print the Arabic
   letters apart. `Dockerfile.ci` takes the same pinned image and adds `fonts-noto-core`
   (Noto Naskh Arabic). T4 prints a real PDF and checks that the font's name is embedded in it.
   It does not check that the letters look joined or that the columns sit side by side: that
   needs a look at a printed page.
3. In a test run, Odoo returns HTML instead of a PDF; the context key `force_report_rendering`
   makes it a real PDF. wkhtmltopdf then fetches the CSS from the Odoo server over HTTP. That
   request waited for the test's transaction, which is never committed, so the test hung. With
   the registry in test mode alone, the requests were refused for lack of the test cookie, and
   the PDF came out without CSS. `allow_pdf_render()` does both: the requests share the test's
   cursor, and wkhtmltopdf sends the test cookie.

---

## Mistakes caught

| Date | Story | What was wrong | How it was caught | Fix |
|---|---|---|---|---|
| 2026-11-22 | 01 | The plan wrote `db_host = False`, `db_port = False` and `db_password = False` in `odoo.conf.example`. In Odoo 19 a `False` value for a non-boolean option logs a `WARNING` and is skipped, which breaks the "no warning in the log" rule. | Reading Odoo 19's config-file parser (`odoo/tools/config.py`) before writing the file | Lines left out; the defaults already mean "local socket, password from `~/.pgpass`" |
| 2026-11-22 | 01 | `http_interface` was not set. Odoo 19 warns that the default `0.0.0.0` (listen on every network) changes to `127.0.0.1` in Odoo 20. | The `make test` log check failed on the first run | `http_interface = 127.0.0.1` in `odoo.conf.example`; CI passes `--http-interface` |
| 2026-11-22 | 01 | The prettier XML plugin was declared in `.prettierrc.yml`, where prettier 3 cannot load it from pre-commit's own Node environment. | `make lint` failed: `Cannot find package '@prettier/plugin-xml'` | Replaced by `prettier.config.cjs` with `require.resolve(...)`, as OCA's template does |
| 2026-11-22 | 01 | A negative check (test import commented out on purpose) was staged and committed before being undone, so the committed module ran no test. | Reviewing the commit before pushing: `git show HEAD:addons/real_estate_eg/tests/__init__.py` | Undo, `make test`, then `git commit --amend` (not yet pushed). Rule: undo negative-check edits before `git add`. |
| 2026-11-23 | 02 | The delivery date was checked only when Deliver was clicked, so a future date typed on the form stayed stored on a contract that was then cancelled instead of delivered. | The maintainer's walk-through: the data showed a cancelled contract with a delivery date in the future | `@api.constrains` on `delivery_date`: checked on every save; the stored value was cleared |
| 2026-11-23 | 02 | The first read-only test (AC-06.3) only tried to edit a confirmed contract, which the Python edit guard already blocks, so it never tested the access rights. | Negative check N4: giving collections officers write rights did not make the test fail | A draft contract added to the test; N4 then failed on four points |
| 2026-11-23 | 02 | The "two contracts for one unit in the same save" test used a unit that already had a contract, so it passed for the wrong reason. | Re-reading the test before committing | A fresh unit, and the test checks the exact message |
| 2026-11-23 | 02 | Plan links to the business rules used `<a id>` anchors, which the review tool's file pane does not follow. | The maintainer clicked the links; a five-way link test showed only heading links work | Each id links to its heading (BR to its group, US and AC to their story), with the rule text as hover title |
| 2026-11-23 | 02 | Two scripted text replacements did not apply after the formatter had re-wrapped the lines, so a test run checked the old code. | Reading the file after the run, before committing | Edited by hand and re-run. Rule: after a scripted edit, check the diff before trusting a test run. |
| 2026-11-24 | 03 | The BR-46 check was first an `@api.constrains`. It runs after the INSERT, so the new unique index refused the duplicate first, without naming the existing contact. | The first test run: a raw `UniqueViolation` instead of the expected `ValidationError` | The check moved before `super()` in `create()` / `write()`, as Story 02's unit check |
| 2026-11-24 | 03 | A new test file was not imported in `tests/__init__.py`, so its five tests never ran and the suite looked green. | The test count stayed at 26 instead of 31 | Import added. Rule: after adding a test file, check the count goes up. |
| 2026-11-24 | 03 | The stale-schedule check deleted a contract's lines on confirmation: filling an empty contract date (BR-07) looked like a date change. | T16 failed with `MissingError` on the deleted lines | Only a change from a date already set drops the schedule; T11 checks the lines survive confirmation |
| 2026-11-24 | 03 | Story 02 left the contract date writable by a manager after confirmation (only the form hid it), so a confirmed schedule's dates could drift from it. | The maintainer asked why the plan said "a manager can still change it" when the form was read-only | `write()` refuses a new date outside draft; Story 02's test now expects the refusal (N7) |
| 2026-11-24 | 01 | `make shell` never worked: `odoo-bin` needs its subcommand first, but the Makefile put `shell` after `-c odoo.conf`. | The maintainer ran `make shell` for the first time | The target calls `odoo-bin shell -c odoo.conf` |
| 2026-11-24 | 03 | The AI ran `make test` while the maintainer's own run was going: same database, port and log file, so one run showed a stale result. | Timestamps: the failing run had ended before the fix was saved | Rule: one test run at a time; wait for the maintainer's run to finish |
| 2026-11-24 | 04 | The shell command given to invoice a line by hand used `fields.Date.today()` without importing `fields`, so it stopped with a `NameError`. | The maintainer ran it on `re_dev` | `from odoo import fields` added to the command; nothing had been created |
| 2026-11-24 | 04 | T6 (the job invoices once) counted lines that have an invoice. A second invoice for the same line only replaced the link, so the count stayed at 2 and the test missed it. | Negative check N2 (no "no invoice yet" filter): T6 still passed | T6 counts the posted invoices in accounting; N2 now fails it |
| 2026-11-25 | 04 | The Example E test helper paid every line numbered 0 to 4, including the maintenance deposit, which has no invoice before delivery. | The first test run: Odoo's "nothing left to pay" error | The helper pays the down payment and installments 1–4 only |
| 2026-11-25 | 08 | The first printed contract showed 10 Jan 2027 as `01/10/2027`, the US date order of the user's language, which an Egyptian reader takes for 1 October. | Looking at the first rendered page | Every date prints `dd/MM/yyyy` (the date widget's `format` option) |
| 2026-11-25 | 08 | The maintenance deposit row was numbered 1: it is printed after the total, by a second loop, and `line_index` restarts at 0 in each loop. The tests checked names and amounts, not numbers. | Looking at the rendered page | Number = place in the whole schedule; T1 now checks 1 to 34 |
| 2026-11-25 | 08 | The real-PDF test hung, then printed a PDF without CSS: wkhtmltopdf's requests for the CSS waited for the test's uncommitted transaction, then were refused for lack of the test cookie. | `make test` stopped at the test; the log showed "ignored during test" for the CSS | `TransactionCase.allow_pdf_render()`: shares the test cursor and adds the cookie |
| 2026-11-25 | 08 | A test run used the same HTTP port as the running dev server, so Odoo could not start and no test ran. | The log check: "no real_estate_eg test ran" (`Address already in use`) | Tests on their own port; the log check is what caught it |
