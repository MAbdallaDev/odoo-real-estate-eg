# Story intake — 08-bilingual-pdf

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `08-bilingual-pdf`

---

## Title

Bilingual Arabic / English contract PDF

---

## Description

Print the contract as one PDF with Arabic and English side by side on the same page — parties, unit,
price, plan and the full schedule — the way Egyptian sale contracts are laid out. This is one report
with two columns, not Odoo's translation system. The UI's own Arabic translation (`i18n/ar.po`) is
separate and optional here.

---

## Acceptance criteria

### User stories

**US-07 — Print the contract in Arabic and English**
*As a **sales agent**, I want to print the contract with Arabic and English side by side, so that the
customer signs one document they can read.*

### Business rules

| ID | Rule |
|---|---|
| BR-38 | The contract prints as one PDF with **Arabic and English side by side**: parties, unit, price, plan, and the full schedule table. |

### Acceptance criteria (from the business document)

- **AC-07.1** The rendered report contains the Arabic and English text for parties, unit, price, plan
  and every schedule line, with the Arabic side marked right-to-left (`dir="rtl"`). *(manual: letters
  joined, columns side by side in the PDF.)*
- **AC-07.2** A 60-character customer name appears in full in the rendered report. *(manual: the layout
  does not break.)*
- **AC-07.3** Amounts show with thousands separators and the currency, e.g. `8,580,000 EGP`.

### Story-level criteria

- **S08.1** An Arabic font (e.g. Noto Naskh Arabic) is installed locally and in the CI image, and
  the setup is written in the README.

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** 03-schedule-generator
- **Depends on code areas or other stories:** Story 03 (schedule lines to print). Can run in parallel with Stories 04–07.

## Extra notes (optional)

Risk: wkhtmltopdf renders Arabic as disconnected letters if the font is missing. If it cannot be made
to work within the story, the English PDF ships and Arabic becomes a follow-up — the README says so.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- QWeb report with its own paper format; Arabic column wrapped in `dir="rtl"`.
- Amount formatting with thousands separators and currency through Odoo's monetary widget/formatting (verify the QWeb option names in Odoo 19).
- Tests render the report to HTML (verify the Odoo 19 API for rendering a report in a test) and assert on content; the joined-letters check is manual.

## Out of scope

- Legal contract wording or clauses beyond the data listed in BR-38.
- E-signature.
- A full Arabic translation of the UI (optional, not a story criterion).
