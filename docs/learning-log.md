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

*Drafted by the AI at the maintainer's request.*

1. Invoiced: debit Receivable 858,000, credit Customer Advances 858,000. Paid: debit
   Outstanding Receipts 858,000, credit Receivable 858,000, matched with the invoice.
   Cancelled while unpaid: a credit note, debit Customer Advances 858,000, credit Receivable
   858,000, matched with the invoice. There is no revenue line because the money still belongs
   to the customer until the unit is handed over: it is an advance, a liability (BR-43).
   Revenue at delivery is v1.1. For the payment to make the line show paid, the bank journal's
   incoming payment method needs an Outstanding Receipts account. Without it the payment has
   no journal entry, so `amount_residual` never drops.
2. Odoo's reversal wizard always credits the whole invoice. For a partly paid invoice, that
   would also "refund" the part the customer really paid. Our credit note is for exactly
   `amount_residual`. The retention comes first because a credit note lowers
   `amount_residual` exactly like a payment does. Computed afterwards, the credited amount
   would look like money received, and the retention and refund would be too high.
3. Agents and collections officers have no rights on invoices, so they cannot read
   `invoice_id`. The state and amounts are copied onto the line (stored) so everyone can read
   them, search them and group by them. The invoicing methods run with `sudo()` because a
   sales manager (and the nightly job) has no accounting rights to create and post invoices,
   and because BR-19 locks the schedule lines of a confirmed contract. Only the superuser
   can link the invoice to a locked line.

### Story 05 — Overdue lines, late fees and the at-risk flag

Questions: [`design-notes/05-late-fees.md`](design-notes/05-late-fees.md#explain-back-questions)

*Drafted by the AI at the maintainer's request.*

1. From 10 Apr to 29 Apr (20 days) the fee is on 241,313. From 30 Apr, the day of the first
   payment, to 24 May (25 days) it is on 100,000. 25 May, the day it is fully paid, is not
   charged. 20 × 241,313 × 1 % ÷ 30 + 25 × 100,000 × 1 % ÷ 30 = 1,608.7533 + 833.3333 =
   2,442.0867. Shown half up to piastres: 2,442.09. Billed half up to whole EGP: 2,442.
   Paid in full on 18 Apr: the line was never more than 7 days past due while unpaid, so it
   was never overdue, and the fee is 0. Paid on 19 Apr: it was overdue on 18 Apr, so all 9
   days from 10 Apr are charged: 9 × 241,313 ÷ 3,000 = 723.94.
2. The fee is a function of the payment history and the as-of date, and the job overwrites
   the stored value every night. An accumulating job would go wrong in all three cases.
   Run twice the same night: it would add the day twice. A skipped night: it would miss that
   day. A payment entered on 25 May but dated 21 May: it would already have charged 21–24 May
   on money that was in fact paid, and could not take it back.
3. `Monetary` rounds to piastres every time a value is set. The fee must stay unrounded
   (3,619.695), so the invoice total is rounded only once (3,620) and the daily amounts
   never drift. So the stored fees are `Float`. The screen totals are `Monetary` on purpose:
   they round once, half up, for display (3,619.70). A collections officer can bill because
   the action first checks the collections or manager group, then creates and posts the
   invoice with `sudo()` inside the module's own method. The amount comes from the stored
   fees, so the officer cannot type it, and the officer gets no general invoicing rights.

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

### Story 06 — Record rules: agents see their own contracts; multi-company

Questions: [`design-notes/06-record-rules.md`](design-notes/06-record-rules.md#explain-back-questions)

*Drafted by the AI at the maintainer's request.*

1. An access right says which **tables** a group may read, write, create or delete. A record
   rule says which **rows** of a table a user may reach. In this module the access rights
   decide that a collections officer can read contracts but never write them. The record
   rules decide that an agent reads only the contracts where they are the agent, and only
   those contracts' schedule lines.
2. Global rules (no groups) are AND-ed: each one narrows what every user sees, managers
   included, which is why a company 2 manager sees nothing of company 1. Group rules apply
   only to members of their groups, and the ones that apply are OR-ed, then AND-ed with the
   global rules. The manager group implies the agent group, so a manager is also an agent
   and the agent rule applies to them. Alone, it would show a manager only their own
   contracts. The manager rule `[(1, '=', 1)]` is OR-ed with it: own contracts OR all
   contracts = all contracts. The groups did not change; a widening rule was added.
3. Reading agent A's contract: the agent rule (own only) and the read-all rule both apply,
   OR-ed, so the user sees it. Editing it: the read-all rule has `perm_read` only, so for a
   write only the agent rule counts, and A's contract is refused with an access error. With
   all four perms, the read-all rule would also count for writes, and since the agent's
   access rights allow writing contracts, this user could edit other agents' drafts.

### Story 07 — Collections screens and query performance

Questions: [`design-notes/07-collections-performance.md`](design-notes/07-collections-performance.md#explain-back-questions)

*Drafted by the AI at the maintainer's request.*

1. The bucket is a stored compute that depends on `days_past_due` and `is_overdue`. Nobody
   edits the line, but the nightly job does: every night it rewrites `days_past_due` on every
   unpaid invoiced line. That write is a change to a dependency, so the ORM recomputes the
   bucket in the same run, and a line moves from "1–30" to "31–60" the night it reaches day 31.
   A payment changes the line's state (read from the invoice). `is_overdue` depends on the
   state, so it becomes False at once, and the bucket depends on `is_overdue`, so it is cleared
   at once too, without waiting for the next night.
2. Story 05's index on `is_overdue` only finds **which** lines are overdue, not in which
   order. To show the 80 most late, PostgreSQL had to fetch all 12,556 overdue lines from the
   table (one page each, about 7,450 buffers) and sort them to keep the top 80. The partial
   index holds only the overdue lines, already sorted by days past due (most late first), so
   PostgreSQL reads the first 80 entries in order and stops: no sort, 82 buffers, 9.1 ms down
   to 0.11 ms. The cost no longer grows with the number of overdue lines.
3. The count and the pivot must read **every** overdue line whatever the index, so the new
   index cannot make them read less. When I tried the partial index alone, the planner used it
   through a bitmap heap scan, and they got slower: the count went from 3.9 to 10.0 ms and the
   pivot from 13.2 to 17.0 ms. With both indexes, the planner uses the partial one for the list
   and the plain one for the count and the pivot, which stay close to before (4.8 and 13.9 ms,
   same buffers). So the measurements said to keep both.

### Story 09 — Post-dated cheques

Questions: [`design-notes/09-post-dated-cheques.md`](design-notes/09-post-dated-cheques.md#explain-back-questions)

*Waiting for the maintainer's answers.*

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
| 2026-11-25 | 05 | The privacy scan ran in the same command as the commit and push, so the plan reached the story branch with a word from the private pattern list. | The scan's output, read after the push | A follow-up commit reworded it. Rule: the scan runs before `git commit`, and a hit stops the commit. |
| 2026-11-25 | 05 | The cancellation test (T13) never ran the nightly job on installment 1's due date. The line was invoiced on the day it was paid, so its effective due date moved to that day and no fee accrued. The code was right (BR-26). | Odoo's "nothing left to pay" error when the test paid a late-fee invoice that was never created | The test runs the job on 10 Apr and 10 Jul, as in real life |
| 2026-11-25 | 05 | T13 expected a 1,206 EGP late-fee invoice for 15 × 241,313 ÷ 3,000. That is 1,206.565, which rounds half up to 1,207. | The test failed: `1207.0 != 1206` | The expected value fixed; the comment shows the unrounded amount |
| 2026-11-25 | 08 | The first printed contract showed 10 Jan 2027 as `01/10/2027`, the US date order of the user's language, which an Egyptian reader takes for 1 October. | Looking at the first rendered page | Every date prints `dd/MM/yyyy` (the date widget's `format` option) |
| 2026-11-25 | 08 | The maintenance deposit row was numbered 1: it is printed after the total, by a second loop, and `line_index` restarts at 0 in each loop. The tests checked names and amounts, not numbers. | Looking at the rendered page | Number = place in the whole schedule; T1 now checks 1 to 34 |
| 2026-11-25 | 08 | The real-PDF test hung, then printed a PDF without CSS: wkhtmltopdf's requests for the CSS waited for the test's uncommitted transaction, then were refused for lack of the test cookie. | `make test` stopped at the test; the log showed "ignored during test" for the CSS | `TransactionCase.allow_pdf_render()`: shares the test cursor and adds the cookie |
| 2026-11-25 | 08 | A test run used the same HTTP port as the running dev server, so Odoo could not start and no test ran. | The log check: "no real_estate_eg test ran" (`Address already in use`) | Tests on their own port; the log check is what caught it |
| 2026-11-25 | 06 | Negative check N2 first gave the multi-company rule the agent group to "switch it off" for the company 2 user. That user is a manager, who has the agent group through `implied_ids`, so the rule still applied and T1 still passed. | The negative check did not fail | N2 uses the accountant group, which the user does not have; T1 then fails. The plan and design note say why. |
| 2026-11-25 | 07 | The plan stored `project_id` on the schedule line because "only stored fields can be grouped". In Odoo 19 a non-stored **related** field is grouped through a JOIN (`_traverse_related_sql()`). | Negative check N1 (un-store it) passed instead of failing | Not stored; N1 replaced by a check that does fail |
| 2026-11-25 | 07 | Replacing Story 05's `is_overdue` index with the new partial index made the count and the pivot slower, and removing `index=True` did not even drop the old index ("Keep unexpected index"). | Measuring every setup in the same loop on 1M lines; reading the upgrade log | Both indexes kept; the trap is in the design note |
| 2026-11-25 | 09 | The chatter test (T3) found no tracked state change: Odoo's test base turns tracking off, and a record created that way is marked "do not track" until the next flush. With tracking turned back on, only the last of two moves in one transaction was logged. | T3 failed twice: no change logged, then only "Cleared" | The test turns tracking on and flushes before and after each move, as separate saves in the browser would. The trap is in the design note. |
