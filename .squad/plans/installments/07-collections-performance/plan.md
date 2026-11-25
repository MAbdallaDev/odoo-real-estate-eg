# 07 — Collections screens and query performance

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/07-collections-performance/intake.md`
- **Branch:** `story/07-collections-performance`
- **Status:** Done Criteria approved 2026-11-25; all steps done; 90 tests green; AC-04.4 waits for the
  maintainer's manual check (M1); in review

---

## Prerequisites

- Stories 01–06 and 08 merged; `main` at `baee6ca`; CI green on `main`; `make test` gives 0 failed
  of 83 tests with a clean log; `make lint` passes.
- Local `main` clean and in sync with `origin/main`.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Local PostgreSQL with `psql` (already used by `make test` through `dropdb`). Nothing new to install.
- Tests use `re_test` and free ports (`make test ARGS="--http-port 8097 --gevent-port 8098"`). The
  performance data goes to its own database, `re_perf`, never to `re_test`, `re_dev` or CI.

## Story Goal

Give the collections officer one place to answer "whom do I call today"
([US-04](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "US-04: See what to chase today")): a **Due this month** list, an **Overdue** list with days past due and accrued late
fee, a **pivot** and a **graph** of overdue amounts by project × aging bucket ([BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice.")), and the
**At risk** filter one click away ([BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own.")). Every list goes through the Story 06 record rules: an
agent sees only their own lines, collections, managers and accountants see all.

Then prove the Overdue list scales: about 1,000,000 schedule lines made with SQL `generate_series` in
`re_perf`, the real query captured from the Odoo log, `EXPLAIN (ANALYZE, BUFFERS)` before and after
an index, and the index declared in the module so it ships with every install. Only measured numbers
go in the design note; if the index does not help, the note says so and why.

Not in this story: a custom JS dashboard; calling or messaging customers from the screen; cheques
(Story 09).

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/07-collections-performance/intake.md` — the ACs and S07.1–S07.3.
- `docs/business-requirements.md` — [US-04](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "US-04: See what to chase today"), [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days)."), [BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own."), [BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice."), §4 rights matrix
  (collections "works the due/overdue screens"), §5.5 nightly job.
- `addons/real_estate_eg/models/real_estate_installment.py` — what is already **stored**:
  `date_due`, `date_effective_due` (stored compute), `state` (stored, indexed), `amount`,
  `amount_residual` (stored Monetary), `days_past_due` (plain Integer written by the nightly job),
  `is_overdue` (stored compute, `index=True`), `late_fee_accrued` (stored Float, unrounded);
  `late_fee_display` is **not** stored (screen rounding only); `company_id` stored and indexed;
  `_order = "contract_id, sequence, id"`. No project, customer or agent on the line yet.
- `addons/real_estate_eg/models/real_estate_contract.py` — `project_id` (related, stored),
  `partner_id`, `unit_id`, `user_id`, `at_risk` (stored, indexed), `_cron_nightly()` →
  `_cron_late_fees()` rewrites `days_past_due` every night on every unpaid invoiced line.
- `addons/real_estate_eg/views/real_estate_contract_views.xml` — the contract search view already
  has the `overdue` and `at_risk` filters (Story 05); the schedule list inside the form.
- `addons/real_estate_eg/views/real_estate_menus.xml` — the root menu and its groups.
- `addons/real_estate_eg/security/ir_rules.xml` — agent rule on lines
  (`contract_id.user_id = user.id`), manager "see all", read-only "see all" for collections and
  accountants, multi-company rules. The new screens add **no** rule.
- `addons/real_estate_eg/security/ir.model.access.csv` — every role already reads
  `real.estate.installment`.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon`: `agent_a`, `agent_b`, `manager`,
  `collections`, `accountant`, `create_contract()`, `_example_a()`, `_confirmed()`.
- `addons/real_estate_eg/tests/test_late_fees.py` — `_installment_1_invoiced()`, `_pay()`,
  `_night()` (the nightly job under `freeze_time`), reused by the new tests.
- `Makefile` — `run`, `test`, `lint`, `test-ci`; `DB ?= re_dev` so `make run DB=re_perf ...` works.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/odoo/orm/table_objects.py` — `class Index(TableObject)`: a model attribute
  `_name_idx = models.Index("(cols) WHERE ...")` becomes `CREATE INDEX {table}_{name} ...` on
  install and upgrade; its definition is stored as the index comment, so a changed definition drops
  and recreates it. Examples: `addons/crm/models/crm_lead.py` (`_default_order_idx =
  models.Index('(priority DESC, id DESC) WHERE active IS TRUE')`),
  `addons/product/models/product_template.py` (`_is_favorite_index`, a partial index).
- `odoo-src/odoo/odoo/orm/fields.py` — `index=` values `True`/`"btree"`, `"btree_not_null"`,
  `"trigram"`; stored computes default to `compute_sudo=True`; related fields to
  `related_sudo=True`.
- `odoo-src/odoo/odoo/tools/date_utils.py` — `parse_date()`: relative dates in domains, e.g.
  `'today =1d'` (first day of this month) and `'today =1d +1m'` (first day of next month).
  `odoo/orm/domains.py` `_optimize_type_date_relative()` applies them on the server for `<`, `<=`,
  `>`, `>=`, `in` (not `=`), so the same domain works in a search filter, an action and a test.
- `odoo-src/odoo/odoo/orm/fields_numeric.py` — `Integer`, `Float`, `Monetary` default
  `aggregator = 'sum'` (pivot and graph measures).
- `odoo-src/odoo/odoo/addons/base/rng/pivot_view.rng`, `graph_view.rng`, `list_view.rng` — allowed
  attributes (`default_order` on list and pivot; `type`, `stacked`, `order` on graph). Pattern:
  `addons/account/views/account_move_views.xml` (`<pivot string="Journal Items" sample="1">`).
- `odoo-src/odoo/odoo/tools/config.py` — `--log-sql` (sets `odoo.sql_db` to DEBUG: every query in
  the log).
- `odoo-src/odoo/addons/web/models/models.py` — `web_search_read()` (the list: one `SELECT ...
  LIMIT 80`, then `search_count(domain, limit=count_limit)` for the pager) and
  `formatted_read_group()` (the pivot and graph).

## Implementation tasks

Small steps, in order, **one commit per step**, each ending with a Key points block (built + ids,
Odoo concept, trap, one-line takeaway). Files are new unless marked *(edit)*. All under
`addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Branch and plan commit.** `git switch -c story/07-collections-performance` from
up-to-date `main`; commit this plan and the overview row.

**Step 1 — Line fields for the screens** (`models/real_estate_installment.py` *(edit)*,
`tests/test_collections.py`, `tests/__init__.py` *(edit)*). *[BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice."), [AC-04.1](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.1: A 'Due this month' list shows every unpaid line due in the current month, with customer, phone, unit, amount and agent."), [AC-04.3](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.3: A pivot shows overdue amounts by project × aging bucket (1–30, 31–60, 61–90, 90+).").*
1. Related fields from the contract: `partner_id`, `partner_phone` (`partner_id.phone`), `unit_id`,
   `user_id` (agent), `project_id` — **not stored**. *Corrected during Step 3:* the first version
   stored `project_id` because "only stored fields can be grouped". That is wrong in Odoo 19 for
   related fields: `_field_to_sql()` in `odoo-src/odoo/odoo/orm/models.py` joins through
   `_traverse_related_sql()` for a non-stored related field, so the pivot groups by project with a
   JOIN to the contract. The maintainer chose not to store it (no copy to keep in sync on 1M rows);
   Step 5 also measures the pivot query.
2. `aging_bucket`: a stored computed Selection `1_30`, `31_60`, `61_90`, `over_90` (labels
   "1–30", "31–60", "61–90", "90+"), empty when the line is not overdue. Depends on `is_overdue` and
   `days_past_due`. The order of the selection is the pivot's column order.
3. "Recompute nightly" needs no new cron step: the bucket depends on `days_past_due`, which the
   nightly job already rewrites on every unpaid invoiced line, so the ORM recomputes the bucket in
   the same run. A payment clears `is_overdue` at once, so the bucket clears too. The §5.5 note and
   the overview say so.
4. Tests T1, T2 first. *Check:* `make test`.

**Step 2 — Due this month and Overdue lists** (`views/real_estate_installment_views.xml`,
`views/real_estate_menus.xml` *(edit)*, `__manifest__.py` *(edit)*, `tests/test_collections.py`
*(edit)*). *[AC-04.1](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.1: A 'Due this month' list shows every unpaid line due in the current month, with customer, phone, unit, amount and agent."), [AC-04.2](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.2: An 'Overdue' list shows every overdue line with days past due and accrued late fee."), [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).").*
1. One collections list view of `real.estate.installment`: contract, customer, phone, unit, agent,
   effective due date, amount, outstanding, days past due, late fee (`late_fee_display`), status,
   bucket; overdue rows in red. Read-only (`create="0" edit="0" delete="0"`).
2. A search view: filters **Due this month** (`state` in scheduled / invoiced / partially paid,
   contract confirmed or delivered, `date_effective_due >= 'today =1d'` and `< 'today =1d +1m'`),
   **Overdue** (`is_overdue = True`), **Contract at risk** (`contract_id.at_risk = True`), **My
   lines** (agent = uid); group by project, agent, bucket.
3. Two window actions, one per AC, each with its own domain and default filter: *Due This Month*
   and *Overdue* (default order days past due, most late first).
4. A **Collections** menu under the root with the two lists, the analysis (Step 3) and **At-Risk
   Contracts** (the contract action opened with `search_default_at_risk`, [AC-04.4](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.4: (manual) Contracts flagged at risk can be filtered in one click.")). Groups:
   collections, manager, accountant (the users §4 gives the due/overdue screens). Agents keep their
   own lines in the contract form; the record rules hold either way.
5. Tests T3, T4, T5. *Check:* `make test`.

**Step 3 — Pivot and graph** (`views/real_estate_installment_views.xml` *(edit)*,
`tests/test_collections.py` *(edit)*). *[AC-04.3](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.3: A pivot shows overdue amounts by project × aging bucket (1–30, 31–60, 61–90, 90+)."), [BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice.").*
1. Pivot: rows `project_id`, columns `aging_bucket`, measure `amount_residual` (the overdue amount
   still owed); graph: bar, `aging_bucket` × `amount_residual`, stacked by project.
2. An *Overdue Analysis* action (pivot, graph, list) with the Overdue domain.
3. Test T6 reads the same numbers through `formatted_read_group` as the collections user.
   *Check:* `make test`.

**Step 4 — Performance data in `re_perf`** (`scripts/perf/README.md`, `scripts/perf/seed.sql`).
*S07.1.*
1. `make run DB=re_perf ARGS="-i real_estate_eg --stop-after-init --http-port 8097 --gevent-port
   8098"` makes an empty database with the module (no demo data).
2. `seed.sql` (run with `psql -d re_perf -f scripts/perf/seed.sql`) fills projects, units, partners,
   contracts and about **1,000,000** lines with `generate_series`, writing the stored columns
   directly (state, `date_effective_due`, `days_past_due`, `is_overdue`, `aging_bucket`,
   amounts), with a stated, realistic mix (most lines future or paid, a few percent
   overdue). Lines get no invoice; the README says this is a load test of one query, not
   accounting data. Ends with `ANALYZE`.
3. Never in the test suite or CI: the file is outside `addons/`, the tests and the CI workflow do not
   reference it.

**Step 5 — Measure, add the index, measure again** (`models/real_estate_installment.py` *(edit)*,
`docs/design-notes/07-collections-performance.md`). *S07.2, S07.3.*
1. **Capture the real query**: open the Overdue list as a collections user against `re_perf` with
   `--log-sql` (the user's browser, or `web_search_read` in `make shell DB=re_perf` with the same
   domain, order and limit). Copy the `SELECT ... LIMIT 80` and the count query from the log, with
   the record-rule conditions Odoo added.
2. **Before**: `EXPLAIN (ANALYZE, BUFFERS)` of both queries in `psql`, each run 3 times, warm cache;
   plan and timings into the design note.
3. **Index**: chosen from that plan, not in advance. Starting candidate: a partial index for the
   overdue rows in list order, e.g. `models.Index("(days_past_due DESC, id) WHERE is_overdue IS
   TRUE")`; the final columns follow the plan. The pivot's `formatted_read_group` query (with its
   JOIN to the contract for the project) is measured too. Whether Story 05's plain `index=True` on `is_overdue`
   stays is decided from the same numbers.
4. `-u real_estate_eg` on `re_perf` (Odoo creates the index), `ANALYZE`, **after** run with the same
   queries. Both plans, timings, buffers and the index size in the note. If the index does not help,
   the note says so and explains why (e.g. selectivity), and the index is not kept for show.
5. Test T7: the index exists after install (catalog `pg_indexes`). *Check:* `make test`.

**Step 6 — Whole flow + CI stack.** On `re_dev`: `-u real_estate_eg`; open the four screens as the
collections user and as an agent; log clean. Then `make lint`, `make test-ci`.

**Step 7 — Docs + PR.** `docs/design-notes/07-collections-performance.md` (stored vs non-stored
fields for screens, bucket recompute through `days_past_due`, relative-date domains, record rules on
the new screens, the perf method and the measured before/after, negative checks; 3 explain-back
questions); `docs/learning-log.md`; `README.md` *(edit)*: roadmap 06 → done (if not already), 07 →
in review. Done Criteria ticked in `plan.md` and `plan.ar.md`. PR; CI green; the maintainer answers
the explain-back questions in `docs/learning-log.md` and merges with "Create a merge commit".

## Edge Cases & Failure Modes

1. **Bucket edges** ([BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice.")): 8 → `1_30` (days 1–7 are inside the grace, not overdue), 30 →
   `1_30`, 31 → `31_60`, 60 → `31_60`, 61 → `61_90`, 90 → `61_90`, 91 → `over_90`.
2. **Grace is a company setting** (Story 05): the bucket follows `is_overdue`, so a company with a
   longer grace has no line in the first bucket until its grace has passed.
3. **Stale buckets**: days past due change daily without any write; the nightly job's rewrite of
   `days_past_due` is what moves a line to the next bucket. If the job did not run, the screen shows
   last night's buckets — same as the late fee.
4. **Due this month uses the effective due date** ([BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).")): a line confirmed late and invoiced
   this month shows this month, not in a past month nobody looks at. Lines not invoiced yet use
   their scheduled date (the effective date falls back to it).
5. **Draft and cancelled contracts**: draft lines are not owed and cancelled lines have state
   `cancelled`; both stay out of Due this month.
6. **Deposit due at delivery** with no date yet ([BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date.")) has no effective date: never in Due
   this month.
7. **Record rules**: the screens add no rule and no `sudo()`; an agent who opens a list by URL sees
   only their own lines; the pivot totals are computed under the same rules.
8. **Not-stored related fields** (customer, phone, unit, agent, project) are grouped, sorted and
   searched through a JOIN to the contract; a non-stored *compute* (not related) could not be grouped,
   which is why `aging_bucket` is stored.
9. **Relative dates** use the user's timezone (`context_today`), so "this month" flips at local
   midnight on the 1st.
10. **Perf data never leaks**: `re_perf` is separate; `make test` drops and recreates only
    `re_test`; the seed is a plain SQL file nothing in `addons/` or CI calls.
11. **A partial index matches only queries whose WHERE implies its predicate**: the Overdue action's
    domain must produce `is_overdue IS TRUE`/`= true` as Odoo writes it; the captured SQL shows it.
12. **Small tables**: in `re_test` the planner scans the table whatever indexes exist; T7 checks the
    index exists, not that it is used.

## Test Plan

Tests under `addons/real_estate_eg/tests/test_collections.py`, `@tagged("post_install",
"-at_install")`, on `RealEstateCommon`. Every check runs `with_user()` as an agent, manager,
collections officer or accountant — never as admin — and nothing relies on demo data. Dates are fixed
with `freeze_time`; the nightly job runs as in `test_late_fees.py`.

| # | Test | Proves |
|---|---|---|
| T1 | `test_bucket_edges` — one invoiced line, nightly job on the days giving 7, 8, 30, 31, 60, 61, 90, 91 days past due: bucket empty, `1_30`, `1_30`, `31_60`, `31_60`, `61_90`, `61_90`, `over_90` | [BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice.") |
| T2 | `test_bucket_cleared_by_payment` — an overdue line paid in full: `is_overdue` and the bucket empty at once, before the next run | [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days)."), [BR-37](../../../../docs/business-requirements.md#collections-documents-and-data "BR-37: Overdue amounts are grouped in aging buckets by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice.") |
| T3 | `test_ac_04_1_due_this_month` — as collections, the *Due This Month* action's domain returns this month's unpaid lines of confirmed contracts (scheduled and invoiced), not paid ones, not next month's, not a draft contract's; customer, phone, unit, amount and agent are readable | [AC-04.1](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.1: A 'Due this month' list shows every unpaid line due in the current month, with customer, phone, unit, amount and agent.") |
| T4 | `test_ac_04_2_overdue_list` — as collections, the *Overdue* action's domain returns exactly the overdue lines, with days past due and the late fee readable | [AC-04.2](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.2: An 'Overdue' list shows every overdue line with days past due and accrued late fee.") |
| T5 | `test_lists_follow_record_rules` — agent B's search with each action's domain does not return agent A's lines; the manager and the accountant see them | [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.") |
| T6 | `test_ac_04_3_pivot` — two projects, lines in different buckets: `formatted_read_group(['project_id', 'aging_bucket'], ['amount_residual:sum'])` as collections gives the expected sums per cell | [AC-04.3](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.3: A pivot shows overdue amounts by project × aging bucket (1–30, 31–60, 61–90, 90+).") |
| T7 | `test_s07_3_index_installed` — the new index is in `pg_indexes` for `real_estate_installment` after install | S07.3 |
| M1 | *(manual, Step 6)* Collections → At-Risk Contracts opens the contract list already filtered on At Risk; the At Risk filter is one click in the contract search | [AC-04.4](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.4: (manual) Contracts flagged at risk can be filtered in one click.") |
| T8 | `make test` (all 83 earlier tests still pass), `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: drop `is_overdue` from the bucket's `@api.depends` → T2 fails (a payment no longer clears the
  bucket). *(Replaces the first N1, "un-store `project_id`", which passed: see Step 1.)*
- N2: move bucket edge 30 into `31_60` → T1 fails.
- N3: drop the `models.Index` declaration → T7 fails.

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/07-collections-performance
make test ARGS="--http-port 8097 --gevent-port 8098"   # T1–T7 + the 83 earlier tests, log clean
make lint                                              # pre-commit green
make test-ci                                           # same tests in the CI Docker stack
make run DB=re_perf ARGS="-i real_estate_eg --stop-after-init --http-port 8097 --gevent-port 8098"
psql -d re_perf -f scripts/perf/seed.sql               # ~1M lines, ends with ANALYZE
psql -d re_perf -c "SELECT count(*) FROM real_estate_installment"
make run DB=re_perf ARGS="--log-sql --http-port 8097 --gevent-port 8098"   # capture the Overdue query
psql -d re_perf -f <captured query with EXPLAIN (ANALYZE, BUFFERS)>       # before / after
make run ARGS="-u real_estate_eg --http-port 8097 --gevent-port 8098"     # Step 6 on re_dev; log clean
gh pr checks                                           # pre-commit + test green on the PR
gh run list --branch main --limit 1                    # green after merge
```

## Done Criteria

- [x] **[AC-04.1](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.1: A 'Due this month' list shows every unpaid line due in the current month, with customer, phone, unit, amount and agent.")** A "Due this month" list shows every unpaid line due in the current month, with
  customer, phone, unit, amount and agent. *Proof:* T3.
- [x] **[AC-04.2](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.2: An 'Overdue' list shows every overdue line with days past due and accrued late fee.")** An "Overdue" list shows every overdue line with days past due and accrued late
  fee. *Proof:* T4 (+ T5 for record rules).
- [x] **[AC-04.3](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.3: A pivot shows overdue amounts by project × aging bucket (1–30, 31–60, 61–90, 90+).")** A pivot shows overdue amounts by project × aging bucket (1–30, 31–60, 61–90,
  90+). *Proof:* T6, with T1–T2 for the buckets.
- [ ] **[AC-04.4](../../../../docs/business-requirements.md#us-04--see-what-to-chase-today "AC-04.4: (manual) Contracts flagged at risk can be filtered in one click.")** *(manual)* Contracts flagged at risk can be filtered in one click. *Proof:* M1.
- [x] **S07.1** About 1,000,000 schedule lines are generated with SQL `generate_series` in a separate
  performance database (`re_perf`) — never in the test suite or CI. *Proof:* `scripts/perf/seed.sql`,
  the row count in the design note, no reference from `addons/` or the CI workflow.
- [x] **S07.2** The "Overdue" list's query is captured with `EXPLAIN (ANALYZE, BUFFERS)` before and
  after the index; both plans and timings are in
  `docs/design-notes/07-collections-performance.md`. *Proof:* the design note (measured numbers
  only).
- [x] **S07.3** The index is declared in the module, so it ships with every install. *Proof:* the
  `models.Index` in `real_estate_installment.py` and T7.
