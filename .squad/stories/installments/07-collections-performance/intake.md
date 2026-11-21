# Story intake — 07-collections-performance

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `07-collections-performance`

---

## Title

Collections screens and query performance

---

## Description

Give collections officers one place to answer "whom do I chase today": a "Due this month" list, an
"Overdue" list with days past due and accrued late fee, a pivot of overdue amounts by project ×
aging bucket, a graph, and saved filters including "At risk".

Then prove the screens scale. Generate about one million schedule lines with SQL in a separate
performance database, capture the overdue query's plan with `EXPLAIN (ANALYZE, BUFFERS)`, add the
index it needs, measure again, and write the before/after in the design note.

---

## Acceptance criteria

### User stories

**US-04 — See what to chase today**
*As a **collections officer**, I want one screen of what is due this month and what is overdue, by
aging bucket, so that I know whom to call today.*

### Business rules

| ID | Rule |
|---|---|
| BR-26 | A line's **effective due date** is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. **Days past due** = today − effective due date. A line is **overdue** when it is not fully paid and today is **after** effective due date + **grace period** (7 days). |
| BR-31 | A contract with any line more than **60 days past due** is flagged **at risk of cancellation**. The system never cancels a contract on its own. |
| BR-37 | Overdue amounts are grouped in **aging buckets** by days past due (BR-26): 1–30, 31–60, 61–90, over 90. Only overdue lines appear, so the first bucket holds days 8–30 in practice. |

### Acceptance criteria (from the business document)

- **AC-04.1** A "Due this month" list shows every unpaid line due in the current month, with customer,
  phone, unit, amount and agent.
- **AC-04.2** An "Overdue" list shows every overdue line with days past due and accrued late fee.
- **AC-04.3** A pivot shows overdue amounts by project × aging bucket (1–30, 31–60, 61–90, 90+).
- **AC-04.4** *(manual)* Contracts flagged at risk can be filtered in one click.

### Story-level criteria

- **S07.1** About 1,000,000 schedule lines are generated with SQL `generate_series` in a separate
  performance database — never in the test suite or CI.
- **S07.2** The "Overdue" list's query is captured with `EXPLAIN (ANALYZE, BUFFERS)` before and after
  the index; both plans and timings are in `docs/design-notes/07-*.md`.
- **S07.3** The index is declared in the module, so it ships with every install.

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** 05-late-fees, 06-record-rules
- **Depends on code areas or other stories:** Story 05 (overdue flags, days past due, accrued fees), Story 06 (lists respect record rules).

## Extra notes (optional)

At 50k rows Postgres would happily scan the whole table and an index would prove nothing — hence ~1M.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- Aging bucket as a stored computed selection field so the pivot can group by it; recompute nightly (days past due change every day without any write).
- The overdue domain is on stored fields only, so it can use an index.
- Capture the SQL Odoo actually runs (e.g. `--log-sql` or the Postgres log) rather than guessing it.
- Index candidates: a partial index on unpaid, overdue lines by effective due date — decide from the measured plan, not in advance.

## Out of scope

- Dashboards beyond list / pivot / graph (e.g. a custom JS dashboard).
- Calling customers or sending reminders from the screen.
