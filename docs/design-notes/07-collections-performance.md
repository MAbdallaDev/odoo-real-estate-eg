# 07 — Collections screens and query performance

Plan: [`.squad/plans/installments/07-collections-performance/plan.md`](../../.squad/plans/installments/07-collections-performance/plan.md)

A collections officer needs one place to answer "whom do I call today" (US-04). Story 07 adds
that place, under **Real Estate → Collections**, then proves the Overdue list stays fast on about
one million schedule lines.

## What was added

| Screen | What it shows | Rules |
|---|---|---|
| Due This Month | unpaid lines of confirmed or delivered contracts whose effective due date is in this month: contract, customer, phone, unit, agent, amount, outstanding | AC-04.1, BR-26 |
| Overdue | overdue lines, most late first, with days past due, late fee and aging bucket | AC-04.2, BR-26 |
| Overdue Analysis | pivot (project × aging bucket) and stacked bar graph of the amount still owed on overdue lines | AC-04.3, BR-37 |
| At-Risk Contracts | the contract list opened with the At Risk filter already on | AC-04.4, BR-31 |

The menu is for collections officers, sales managers and accountants (§4 rights matrix). The
screens add **no record rule and no `sudo()`**: an agent who opens one by URL sees only their own
lines (T5), as Story 06 decided.

On the line (`models/real_estate_installment.py`):

- `aging_bucket`: a stored computed selection `1_30`, `31_60`, `61_90`, `over_90`, empty when the
  line is not overdue (BR-37).
- `partner_id`, `partner_phone`, `unit_id`, `user_id`, `project_id`: related fields through the
  contract, **not stored**.
- `_overdue_order_idx`: a partial index for the Overdue list (S07.3, below).

## The aging bucket needs no cron step

Days past due change every day without any write, so a stored bucket could go stale. But the
nightly job (Story 05, §5.5 step 2) already rewrites `days_past_due` on every unpaid invoiced
line. The bucket depends on `days_past_due` and `is_overdue`, so the ORM recomputes it in the
same run. A payment changes the line's state, which clears `is_overdue` at once, which clears
the bucket at once (T2). One job, one source of truth.

The bucket counts days **past due**, not days past the grace period. With the default 7 days of
grace, day 8 is the first overdue day and falls in "1–30" (T1 checks days 7, 8, 30, 31, 60, 61,
90, 91).

## Grouping by a related field that is not stored

The plan first stored `project_id` on the line because "only stored fields can be grouped". That
is wrong in Odoo 19 for **related** fields: `_field_to_sql()` in `odoo/orm/models.py` handles a
non-stored related field with `_traverse_related_sql()`, which adds a JOIN to the contract. The
pivot groups by project through that JOIN (the measured pivot query below shows it). The
maintainer chose not to store it: no copy of the project to keep in sync on a million lines.

A non-stored **computed** field (not related) has no column to join to, so it cannot be grouped.
That is why `aging_bucket` is stored.

## "This month" in a domain

Odoo 19 domains accept relative dates: `'today =1d'` is the 1st of this month and
`'today =1d +1m'` the 1st of next month (`odoo/tools/date_utils.py`, `parse_date()`). The server
turns them into dates in the user's timezone (`_optimize_type_date_relative()` in
`odoo/orm/domains.py`), for `<`, `<=`, `>`, `>=` and `in` only. The same domain works in the
action, the search filter and the tests (with `freeze_time`).

Due This Month uses the **effective** due date (BR-26). A line confirmed late and invoiced this
month shows this month, not in a past month that nobody opens.

The domain is on the **action**, not only a default filter, so removing the filter in the search
bar cannot widen the list. Window actions have no sort order in Odoo 19, so the Overdue list is a
second list view (`mode` primary, inheriting the first) with `default_order="days_past_due desc,
id"`.

## Performance (S07.1 – S07.3)

### The data

`scripts/perf/seed.sql` fills a separate database, `re_perf`, with plain SQL (`generate_series`).
It is never used by `make test`, `make test-ci` or CI.

| | Count |
|---|---|
| Schedule lines | **1,000,000** (25,000 contracts × 40 lines) |
| Overdue lines | 12,556 (1.26%) |
| by bucket 1–30 / 31–60 / 61–90 / 90+ | 1,437 / 1,947 / 1,821 / 7,351 |
| Line states: scheduled / paid / invoiced / partially paid | 700,205 / 286,675 / 9,108 / 4,012 |
| At-risk contracts | 7,713 of 25,000 |
| Table size | 145 MB |

The seed took 17 s. PostgreSQL 16.15, local, default settings.

### The real queries

Captured from the Odoo log (`--log-sql`) while a collections user (`perf_collections`) ran the
Overdue action's domain through `web_search_read()` (the list, limit 80, as the web client) and
`formatted_read_group()` (the pivot). Odoo added the multi-company rule `company_id IN (1)`; the
collections "read all" rule adds nothing.

```sql
-- The list (selected columns shortened)
SELECT "real_estate_installment"."id", ... FROM "real_estate_installment"
WHERE "real_estate_installment"."is_overdue" IS TRUE
  AND "real_estate_installment"."company_id" IN (1)
ORDER BY "real_estate_installment"."days_past_due" DESC, "real_estate_installment"."id"
LIMIT 80;

-- The pager's count
SELECT COUNT(*) FROM (SELECT FROM "real_estate_installment"
WHERE "real_estate_installment"."is_overdue" IS TRUE
  AND "real_estate_installment"."company_id" IN (1) LIMIT 10001) t;

-- The pivot (project through a JOIN to the contract)
SELECT "real_estate_installment__contract_id"."project_id", "real_estate_installment"."aging_bucket",
       SUM("real_estate_installment"."amount_residual")
FROM "real_estate_installment"
LEFT JOIN "real_estate_contract" AS "real_estate_installment__contract_id" ON (...)
LEFT JOIN "real_estate_project" AS "real_estate_installment__project_id" ON (...)
WHERE "real_estate_installment"."is_overdue" IS TRUE AND "real_estate_installment"."company_id" IN (1)
GROUP BY ... ORDER BY "real_estate_installment__project_id"."code", "real_estate_installment"."aging_bucket";
```

### Before: the list sorts every overdue line

Story 05 already indexed `is_overdue`. The planner uses it, reads **all 12,556 overdue lines**
(one heap page each, 7,450 buffers), then keeps the 80 most late with a top-N sort:

```text
Limit  (actual time=8.978..8.986 rows=80 loops=1)
  Buffers: shared hit=7450 read=13
  ->  Sort  (actual time=8.977..8.982 rows=80 loops=1)
        Sort Key: days_past_due DESC, id
        Sort Method: top-N heapsort  Memory: 42kB
        ->  Index Scan using real_estate_installment__is_overdue_index on real_estate_installment
              (actual time=0.012..6.121 rows=12556 loops=1)
              Index Cond: (is_overdue = true)
              Filter: (company_id = 1)
Execution Time: 9.013 ms
```

Without any index (for reference, separate run): a parallel sequential scan of the whole table,
about 35 ms for the list and 42 ms for the pivot.

### The index

Chosen from that plan: the list wants overdue lines only, already in its order.

```python
_overdue_order_idx = models.Index(
    "(days_past_due DESC, id) WHERE is_overdue IS TRUE"
)
```

`models.Index` (`odoo/orm/table_objects.py`) creates `real_estate_installment_overdue_order_idx`
on install and upgrade, and stores its definition as the index comment, so a changed definition
is recreated. It holds only the 12,556 overdue lines: **296 kB**, against 6.3 MB for the full
`is_overdue` index.

### After: the list reads 80 entries

```text
Limit  (actual time=0.019..0.247 rows=80 loops=1)
  Buffers: shared hit=82
  ->  Index Scan using real_estate_installment_overdue_order_idx on real_estate_installment
        (actual time=0.018..0.240 rows=80 loops=1)
        Filter: (company_id = 1)
Execution Time: 0.273 ms
```

No sort. 82 buffers: the index pages plus one heap page per row shown.

### Timings

`EXPLAIN (ANALYZE, BUFFERS)`, warm cache. Wall-clock times on this machine move by up to 2× from
one batch to the next with the **same plan and buffers**, so the three setups were measured in
the same loop, one after the other, 8 rounds; the first round is a warm-up, the table shows the
median of the other 7. Buffers are the steady number.

| Query | Before (Story 05 index) | Partial index only | **Both (shipped)** |
|---|---|---|---|
| List, first 80 | 9.09 ms, 7,450 buf | 0.28 ms, 82 buf | **0.11 ms, 82 buf** |
| Count (pager) | 3.86 ms, 5,658 buf | 10.03 ms, 5,683 buf | 4.79 ms, 5,647 buf |
| Pivot | 13.19 ms, 7,963 buf | 17.03 ms, 7,986 buf | 13.89 ms, 7,961 buf |

What the numbers say:

- **The list**: about 80× faster, 90× fewer buffers. It no longer depends on how many lines are
  overdue, only on the page size.
- **The count and the pivot** must read every overdue line whatever the index, so the new index
  cannot help them. With the partial index **only**, the planner used a bitmap heap scan on it and
  they got slower. So Story 05's plain index stays. With both, the planner picks the partial index
  for the list and the plain one for the count and the pivot. Their small rise against "before"
  comes with the same buffers; it is within the noise described above, not a new cost.
- **In real time** the whole Overdue screen is now about 5 ms of SQL instead of 13; on this data
  neither is slow for a person. The index matters as overdue lines grow: the old plan grows with
  them, the new one does not.

### A trap found on the way

The first try removed `index=True` from `is_overdue`. On `-u`, Odoo logged `Keep unexpected index
real_estate_installment__is_overdue_index` and left it in place (`check_indexes()` in
`odoo/orm/registry.py`). Removing a field's index only changes **new** databases. Dropping it on
existing ones needs a migration script or a manual `DROP INDEX`.

## Tests

`tests/test_collections.py`, all as real users (collections, agents, manager, accountant), with
`freeze_time`:

| Test | Proves |
|---|---|
| `test_bucket_edges` | days 7 / 8 / 30 / 31 / 60 / 61 / 90 / 91 → empty / 1–30 / 1–30 / 31–60 / 31–60 / 61–90 / 61–90 / 90+ (BR-37) |
| `test_bucket_cleared_by_payment` | a payment clears the bucket at once (BR-26, BR-37) |
| `test_ac_04_1_due_this_month` | this month's unpaid lines, invoiced or not; not a draft's, not a paid one, not March's or May's; customer, phone, unit, amount, agent readable (AC-04.1) |
| `test_ac_04_2_overdue_list` | exactly the overdue line, with days past due, late fee and bucket (AC-04.2) |
| `test_lists_follow_record_rules` | agent B sees none of A's lines; A, manager, accountant do (BR-35) |
| `test_ac_04_3_pivot` | two projects, two buckets: the exact sums per cell, read with `formatted_read_group` as collections (AC-04.3) |
| `test_s07_3_index_installed` | both indexes exist after install, with the model's definition (S07.3) |

The Story 05 helpers (`_installment_1_invoiced()`, `_pay()`, `_night()`) moved to
`tests/common.py`. Total: 90 tests. AC-04.4 is checked by hand (M1).

**Negative checks** (seen failing, then undone before `git add`):

| Check | Change | Result |
|---|---|---|
| N1 | drop `is_overdue` from the bucket's `@api.depends` | T2 fails: the paid line keeps `31_60` |
| N2 | put day 30 in `31_60` | T1 fails: `'31_60' != '1_30'` |
| N3 | remove the `models.Index` | T7 fails |

The first N1, "un-store `project_id`", **passed**: that is how the related-field JOIN was found.

## Alternatives considered

- **A stored `project_id` on the line.** Not needed for grouping (above); it would be a second copy
  to keep in sync. If the pivot's JOIN ever became the slow part, this is the fix, with numbers.
- **The bucket as a non-stored compute.** Always fresh, but it cannot be grouped, so no pivot.
- **A separate cron step for the bucket.** Two jobs writing related facts can disagree; depending
  on `days_past_due` keeps one source.
- **An index on `(company_id, days_past_due DESC, id)`.** With one company the planner filters
  80 rows anyway; with several companies an `IN` list would break the order. Not measured as
  better, so not added.
- **A materialised view or a SQL view (`_auto = False`) for the pivot.** More moving parts for
  14 ms. Not justified by these numbers.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-07--collections-screens-and-query-performance).

1. Days past due change every day, but nobody edits a line. How does the stored aging bucket
   still move from "1–30" to "31–60", and why does a payment clear it before the next night?
2. Before the new index, the planner already used an index for the Overdue list. Why was it still
   reading 7,450 buffers for an 80-row page, and what exactly does the partial index change?
3. Why did Story 05's plain `is_overdue` index stay, even though the new index also covers every
   overdue line? Use the measured count and pivot numbers.
