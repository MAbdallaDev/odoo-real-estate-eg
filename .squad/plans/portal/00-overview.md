# portal — plan overview

Entry point for the **portal** feature: what customers use, in its own addon
`addons/real_estate_eg_portal/` (v1.1). The backend it builds on (contracts, schedules, and
reservations from Story 11) is the **installments** feature, in `real_estate_eg`.

Each story's input is its intake under `.squad/stories/portal/<NN-slug>/intake.md`. Its plan lives in
a folder with the same name, `.squad/plans/portal/<NN-slug>/plan.md`. `NN` continues the global
sequence after the installments stories (`naming.globalSequence` in `config.yaml`).

## Stories

| NN | File | Title | Tracker id | Depends on |
|----|------|-------|------------|------------|
| 12 | `12-portal-api/plan.md` | Customer portal REST API (v1.1) | — | installments 11 |
| 13 | `13-portal-owl/plan.md` | Customer screens in OWL under `/my/...` (v1.1) | — | 12 |

## Dependency notes

- **The business rules stay in `real_estate_eg`.** The portal addon only exposes them to customers
  (access rights, record rules, controllers, screens) and never edits backend files, so the backend
  installs and works without it.
- **Story 13** first decides how the OWL screens call the Story 12 API with the browser session
  (`auth="bearer"` accepts a session only for page navigation, not for `fetch()`).
