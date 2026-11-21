# Story intake — 10-ship

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `10-ship`

---

## Title

Ship v1.0.0: unit import, demo data, README

---

## Description

Make the module something a stranger can install and understand in two minutes. Add a unit import
wizard (repeatable, matched by unit code, all-or-nothing with row-level errors), demo data built from
Nile Heights Developments (Chapter 6), and the README a reviewer reads: screenshots, a 60-second demo
GIF, design-notes index, coverage report and test count. Run the end-to-end checklist and the manual
acceptance checks, then tag `v1.0.0`.

---

## Acceptance criteria

### User stories

**US-08 — Import units from a spreadsheet**
*As an **administrator**, I want to import units from a spreadsheet, so that a developer moving to
Odoo does not retype hundreds of records.*

### Business rules

| ID | Rule |
|---|---|
| BR-39 | Importing **units** from a spreadsheet is **repeatable**: importing the same file again updates the existing units, matched by unit code, and creates no duplicates. A file is imported **all or nothing**: if any row is wrong, nothing is imported and every bad row is reported with its row number and reason. Importing existing contracts is outside v1 (Chapter 7). |

### Acceptance criteria (from the business document)

- **AC-08.1** Given a file of 200 units, importing it creates 200 units.
- **AC-08.2** Importing the same file again creates nothing new; a changed price in the file updates
  the existing unit.
- **AC-08.3** Given a file where one row names an unknown project, nothing is imported and the error
  gives that row's number and reason.

### Story-level criteria

- **S10.1** Installing `real_estate_eg` with demo data on a fresh database gives no error and no
  warning in the log. Demo data: the three projects, unit types and prices, the five plan templates,
  the collection policy, the five people as users in their groups, and contracts in every state.
- **S10.2** README has screenshots, a 60-second demo GIF, the design-notes index, test count and
  coverage, and the "possible next" list from Chapter 7 (ETA named correctly: `l10n_eg_edi_eta`).
- **S10.3** The project plan's end-to-end checklist passes, including the manual checks AC-04.4,
  AC-07.1 and AC-07.2.
- **S10.4** Every `US-xx` has at least one test naming it; the suite is green in CI.
- **S10.5** `CHANGELOG.md` has the `1.0.0` entry and the `v1.0.0` tag is pushed.

### Reference data (test fixtures)

#### 6.1 Projects

| Code | Project | Location | Type | Price / m² (EGP) | Expected delivery |
|---|---|---|---|---|---|
| HNC | **Horizon New Cairo** — هورايزون القاهرة الجديدة | New Cairo | Apartments | 52,000 | Q4 2029 |
| PSS | **Palm Shores Sahel** — بالم شورز الساحل | North Coast | Chalets, twin houses | 68,000 | Q2 2030 |
| CBP | **Capital Business Park** — كابيتال بيزنس بارك | New Administrative Capital | Offices, retail | 61,000 (retail 95,000) | Q4 2028 |

#### 6.2 Unit types and list prices

| Project | Type | Area m² | List price (EGP) |
|---|---|---|---|
| HNC | 2-bedroom apartment | 125 | 6,500,000 |
| HNC | 3-bedroom apartment | 165 | 8,580,000 |
| HNC | Duplex | 240 | 12,480,000 |
| PSS | Chalet | 95 | 6,460,000 |
| PSS | Twin house | 210 | 14,280,000 |
| CBP | Office, small | 60 | 3,660,000 |
| CBP | Office, large | 140 | 8,540,000 |
| CBP | Retail unit | 45 | 4,275,000 |

Unit codes: `<project>-<building>-<floor><unit>`, e.g. `HNC-B07-0302` = Horizon, building 7, floor
03, unit 02.

#### 6.3 Payment plan templates

| Code | Name | Down | Installments | Frequency | First installment | Maintenance | Maintenance due |
|---|---|---|---|---|---|---|---|
| `NH-STD-8Q` | Standard 8 years | 10% | 32 | Quarterly | +3 months | 8% | At delivery |
| `NH-EXT-10Q` | Extended 10 years | 5% | 40 | Quarterly | +3 months | 8% | At delivery |
| `NH-SAHEL-7Q` | Sahel 7 years | 10% | 28 | Quarterly | +3 months | 10% | At delivery |
| `NH-BIZ-5M` | Business 5 years | 20% | 60 | Monthly | +1 month | 10% | At signing |
| `NH-CASH` | Cash | 100% | 0 | — | — | 8% | At delivery |

#### 6.4 Collection and cancellation policy

| Setting | Value | Rule |
|---|---|---|
| Grace period | 7 days | BR-26 |
| Late fee rate | 1% per month, daily, simple (company setting) | BR-27 |
| Late fee cap | 10% of the line | BR-28 |
| At-risk threshold | more than 60 days past due | BR-31 |
| Retention on cancellation | 15% of amount paid on down payment + installments (company setting) | BR-33 |
| Invoice lead days | 0 | BR-22 |
| Accounts | Customer advances; maintenance deposit liability (both configurable) | BR-23, BR-43 |

**Legal note on the rate.** 1% a month is 12% a year. Egyptian Civil Code Art. 227 caps agreed
interest at 7% a year, and courts can reduce penalty clauses they find excessive. The rate here is
illustrative, which is why it is a company setting: a real developer sets it with its lawyer.

#### 6.5 People (all fictional)

| Name | Role |
|---|---|
| Omar Fathy | Sales manager |
| Salma Adel | Sales agent |
| Karim Nabil | Sales agent |
| Hoda Samir | Collections officer |
| Tarek Mansour | Accountant |

Customers in demo data are generated, with obviously fictional names and national IDs.

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** 01–08 (09 if it shipped)
- **Depends on code areas or other stories:** Every earlier story.

## Extra notes (optional)

If time runs short, cut features — never the tests or the README.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- Import wizard: upload a CSV, validate every row first, then create/update in one transaction; unit code is the match key (BR-39).
- Demo data in `demo/` XML/CSV; tests must never depend on it.
- Coverage via `coverage run` around the Odoo test command; publish the percentage in the README.

## Out of scope

- Importing existing contracts (Chapter 7).
- Publishing on the Odoo Apps store.
- Any hosted demo instance.
