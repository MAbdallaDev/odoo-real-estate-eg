# Performance data (Story 07)

A load test for the collections screens: about 1,000,000 schedule lines in a
**separate** database, `re_perf`. Never used by `make test`, `make test-ci` or
GitHub CI.

```bash
# 1. An empty database with the module (no demo data)
make run DB=re_perf ARGS="-i real_estate_eg --stop-after-init"
# 2. Fill it (about 20 s); refuses to run if contracts already exist
psql -v ON_ERROR_STOP=1 -d re_perf -f scripts/perf/seed.sql
# 3. Start over
dropdb --force re_perf
```

What `seed.sql` makes, with plain SQL (`generate_series`), in the main company:

- 10 projects, 25,000 units, 25,000 customers, 25,000 contracts (85% confirmed,
  10% delivered, 5% draft), all with the admin user as agent;
- 40 lines per contract (a 10% down payment, then 39 quarterly installments):
  **1,000,000 lines**. A line already due is paid, except 25% of the lines due
  in the last 120 days and 2% of older ones. About 1.3% of all lines end up
  overdue.

It writes the stored computed columns (state, amounts, days past due, overdue,
aging bucket, late fee, at risk) directly, because no ORM code runs. Lines have
no invoice: this is load-test data for one query, not accounting data. The
numbers depend on the day it runs (`current_date`).

The measurements are in `docs/design-notes/07-collections-performance.md`.
