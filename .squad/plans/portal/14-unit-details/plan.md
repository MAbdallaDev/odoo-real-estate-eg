# 14 — Unit photos, plans offered and unit page (v1.1)

- **Feature:** `portal`
- **Intake:** `.squad/stories/portal/14-unit-details/intake.md`
- **Branch:** `story/14-unit-details`, pull request into **`release/1.1`** (never `main`)
- **Status:** code and tests written 2026-11-28; not yet tested locally by the maintainer

---

## Prerequisites

- `story/14-unit-details` created from `origin/release/1.1` at `120ef1c` (Story 13 merged, PR #19,
  CI green).
- No local Odoo: tests run in GitHub CI. Local checks: `py -3.12 -m pre_commit run --all-files`.
- Odoo 19 symbols used: `image.mixin`, `fields.Image`, `ir.binary._get_image_stream_from`,
  `Stream.get_response`, `Model._read_group`, OWL `markup`.

## Story Goal

US-17: customers see photos, the floor plan, the project and the cost of each plan the project is
sold with, on a page per unit. BR-61 to BR-63.

**Prime constraint:** no file of `real_estate_eg` changes. No existing test is edited. Story 12
clients only get new fields and endpoints.

## What changes outside the new files (and why it is safe)

| File | Change | Why earlier stories are unaffected |
|---|---|---|
| `controllers/main.py` | `image_url` on units; `/units/<id>` gives details; new `/projects`, `/images/<id>`, `/units/<id>/floor-plan` | additive JSON fields; the Story 12 tests read named fields only |
| `controllers/openapi.py` | the new endpoints and schemas | the OpenAPI test requires every route documented, which it is |
| `controllers/portal.py`, `views/portal_templates.xml` | unit page route and breadcrumb | new route; other pages unchanged |
| `security/*` | portal read on plan templates and photos; photo rules (portal, multi-company) | read only, portal group; no staff rule changed |
| `static/src/js/unit_list.js`, `xml`, `scss` | photos and banners on the list, `UnitDetail`, `RequestSent` | the list keeps its filters, pager and request form |
| `__manifest__.py` | 19.0.1.2.0, new view file | — |

New files: `models/real_estate_image.py` (photo model; project and unit fields),
`models/real_estate_plan_template.py` (`_portal_preview`), `views/real_estate_image_views.xml`
(tab *Customer Portal* on project and unit forms), `tests/test_unit_details.py`.

## Steps

1. Mockup with photos and the unit page, agreed with the maintainer. **Done.**
2. Spec: US-17, BR-61–BR-63. **Done.**
3. Models, security, staff views. **Done.**
4. API and OpenAPI. **Done.**
5. Portal: banners, photo cards, unit page. **Done.**
6. Tests. **Done.**
7. Independent review, CI green.
8. Maintainer: upload photos, a floor plan and plans on a project locally; open the unit page as a
   customer. **Pending (rule 1).**

## Tests

| Test | Covers |
|---|---|
| `test_us_17_unit_details` | AC-17.1, BR-61, BR-63 |
| `test_ac_17_unit_without_photos_shows_the_project_photos` | AC-17.1, BR-61 |
| `test_ac_17_plans_offered_on_the_unit_price` | AC-17.2, BR-62 (against a real contract schedule) |
| `test_ac_17_images_follow_the_unit_rule` | AC-17.3, BR-61 (permission denied → 404, bad size → 400) |
| `test_ac_17_projects_with_available_units` | AC-17.3 |
| `test_ac_17_unit_page` | AC-17.4, BR-63 |
| `test_ac_17_rights_on_photos` | AC-17.5 |
| **the v1, Story 11, 12 and 13 tests, unchanged** | AC-17.5 |

## Done Criteria

- [ ] AC-17.1 – AC-17.5 proven by the tests above, green in CI.
- [ ] `git diff origin/release/1.1 -- addons/real_estate_eg/ addons/real_estate_eg_portal/tests/test_portal_api.py addons/real_estate_eg_portal/tests/test_portal_pages.py` is empty.
- [ ] CI log clean.
- [ ] Maintainer's local check (step 8).
