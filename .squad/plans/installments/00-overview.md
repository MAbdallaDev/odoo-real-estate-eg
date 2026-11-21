# installments — plan overview

Entry point for the **installments** feature. Stories execute in order by their `NN` prefix.

Each story's input is its intake under `.squad/stories/installments/<NN-slug>/intake.md`. Its plan lives
in a folder with the same name, `.squad/plans/installments/<NN-slug>/plan.md`, so a story's intake and
plan are easy to pair. A plan file is written just before its story starts (not all at once), because each plan cites files that must exist
and be read first.

## Stories

| NN | File | Title | Tracker id | Depends on |
|----|------|-------|------------|------------|
| 01 | `01-env-skeleton/plan.md` | Environment and module skeleton | — | — |
| 02 | `02-core-models/plan.md` *(not written yet)* | Core models, views, states and access rights | — | 01 |
| 03 | `03-schedule-generator/plan.md` *(not written yet)* | Payment plan templates and the schedule generator | — | 02 |
| 04 | `04-accounting-link/plan.md` *(not written yet)* | Accounting link: invoices, payment state, closing and cancellation money | — | 03 |
| 05 | `05-late-fees/plan.md` *(not written yet)* | Overdue lines, late fees and the at-risk flag | — | 04 |
| 06 | `06-record-rules/plan.md` *(not written yet)* | Record rules: agents see their own contracts; multi-company | — | 05 |
| 07 | `07-collections-performance/plan.md` *(not written yet)* | Collections screens and query performance | — | 05, 06 |
| 08 | `08-bilingual-pdf/plan.md` *(not written yet)* | Bilingual Arabic / English contract PDF | — | 03 |
| 09 | `09-post-dated-cheques/plan.md` *(not written yet)* | Post-dated cheques (stretch) | — | 04, 07 |
| 10 | `10-ship/plan.md` *(not written yet)* | Ship v1.0.0: unit import, demo data, README | — | 01–08 (09 if shipped) |

## Dependency notes

- **Critical path:** 01 → 02 → 03 → 04 → 05 → 06 → 07 → 10. Story 08 needs only 03, so it can be
  pulled earlier if a story is blocked.
- **The nightly job** is created in Story 04 (invoice due lines, close paid contracts); Story 05 adds
  the late-fee and at-risk steps; Story 07 adds the aging-bucket recompute.
- **Security** is split on purpose: groups and access rights in 02 so every later test runs as a real
  user; record rules in 06 once every model they must cover exists.
- **Story 09 is a stretch.** If time runs short it moves to v1.1 and Story 10 ships without it.
- **Maintainer-written code:** the schedule arithmetic (03) and the agent record rule (06). Their
  plans mark those tasks explicitly, tests first.
