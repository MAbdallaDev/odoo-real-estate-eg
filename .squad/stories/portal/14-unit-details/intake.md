# Story intake — 14-unit-details

> **Source:** manual entry (no tracker). Rules, user story and acceptance criteria below are pasted
> from `docs/business-requirements.md` (v1.1 scope change, 2026-11-28). If they ever disagree, that
> document wins.

---

## Feature

- **Feature name (display):** Customer portal (addon `real_estate_eg_portal`)
- **Feature slug (folder under `plans/`):** `portal`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `14-unit-details`

---

## Title

Unit photos, plans offered and unit page (v1.1)

---

## Description

After seeing the Story 13 pages, the maintainer asked for a portal that sells: photos on the units
page and a page per unit with its photos, facts, floor plan, payment plans and project. Staff add
the photos, the floor plan, the project's description and the plans each project is sold with.

**Prime constraint (maintainer):** no file of `real_estate_eg` changes; everything is added by
`real_estate_eg_portal` (`_inherit`). The v1, Story 11, 12 and 13 tests pass **unchanged**.

### Decisions (maintainer, 2026-11-28)

- **One story** (not split): staff fields, API and pages depend on each other.
- **Photos** on the project (the first is the cover) and on the unit; a unit without photos shows
  its project's (developers usually photograph a model, not every flat).
- **Floor plan** = one image uploaded per unit (the engineer's drawing), not drawn from data.
- **Plans offered per project** (option 1): a new field on the project listing the plan templates
  it is sold with; the unit page shows only those, worked out on the unit's price. Rejected: showing
  every plan (a customer could see a plan the project is not sold with).
- **Project description**: one free text (HTML) field, not separate fields for area or buildings.
  The expected delivery date already exists on the project.
- Mockup with photos and the unit page shown first (private artifact, fake data).

---

## Acceptance criteria

### User story

**US-17 — See a unit before I ask for it *(v1.1)***
*As a **customer**, I want to see photos, the floor plan, the project and what each payment plan
would cost me for a unit, so that I can choose before I ask for a reservation.*

### Business rules

| ID | Rule |
|---|---|
| BR-61 | Photos on projects and units (ordered, first = cover), floor plan on units; a unit without photos shows its project's; a unit's images follow the unit rule (else not found); project photos are public; images served by the API; projects list for the banners. |
| BR-62 | A project lists the plans it is sold with; the unit shows only those, worked out on its list price as a schedule signed today (BR-15–BR-18); nothing saved; a plan giving a line ≤ 0 is left out. |
| BR-63 | A portal page per unit: photos, facts, floor plan, plans, project, reservation amount, request form while available; list cards show the cover and link to it; a unit the customer may not see is not found. |

### Acceptance criteria (from the business document)

- **AC-17.1** Details: photos in order, floor plan, project; no photos → the project's.
- **AC-17.2** Only the project's plans, with the generator's numbers (same as a contract schedule).
- **AC-17.3** Images of a unit the customer may not see → 404; bad size → 400; projects list.
- **AC-17.4** Unit page for a customer; held unit → 404; staff → `/my`. *(manual: gallery, tabs,
  request in a browser.)*
- **AC-17.5** Customers and agents read photos only; managers add them; one owner per photo;
  US-15 / US-16 suites unchanged.

### Endpoints and pages

| Method | Path | AC |
|---|---|---|
| GET | `/api/v1/units/<id>` (now with `images`, `floor_plan_url`, `plans`, `project`) | AC-17.1, AC-17.2 |
| GET | `/api/v1/units` (now with `image_url`) | AC-17.1 |
| GET | `/api/v1/projects` | AC-17.3 |
| GET | `/api/v1/images/<id>?size=`, `/api/v1/units/<id>/floor-plan` | AC-17.3 |
| page | `/my/real-estate/units/<id>` (`UnitDetail`) | AC-17.4 |

---

## Dependencies

- **Blocked by / related ids:** 13-portal-owl (pages, auth, API service; merged, PR #19),
  03 (schedule generator `tools/schedule.py`).

## Technical hints (optional)

- `image.mixin` for the photo sizes; `ir.binary._get_image_stream_from()` to answer an image.
- The image record rule copies the unit rule through `unit_id`.
- `compute_schedule()` of `real_estate_eg/tools/schedule.py` for the plan preview.

## Out of scope

- Videos, 360° tours, PDF brochures; drawing floor plans from room data.
- Photos per unit model / type (photos are per unit, with the project's as fallback).
- Discounts per plan, prices per plan (the list price is the one price, as in v1).
