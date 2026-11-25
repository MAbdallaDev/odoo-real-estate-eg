# 08 — Bilingual Arabic / English contract PDF

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/08-bilingual-pdf/intake.md`
- **Branch:** `story/08-bilingual-pdf`
- **Status:** Done Criteria approved 2026-11-25; in progress

---

## Prerequisites

- Story 03 merged (PR #3, merge commit `89908b9`); CI green on `main`. The branch is cut from it.
- Story 04 is built **at the same time** on `story/04-accounting-link`. This story uses no Story 04
  field, so the two meet only in shared files (`__manifest__.py`, `tests/__init__.py`, README,
  learning log). Whichever merges second rebases on `main` first.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- wkhtmltopdf 0.12.6.1 with patched Qt (README *Requirements*), locally and in the CI image.
- **Arabic font.** Locally: Debian / Ubuntu package `fonts-noto-core`, which holds Noto Naskh
  Arabic (`fc-list | grep "Noto Naskh Arabic"` shows it). The pinned CI image `odoo:19.0` has no
  Arabic font (`fc-list` lists none): Step 1 adds it.
- Isolated from Story 04 while both run: tests use `make test TEST_DB=re_test_08 ARGS="--http-port
  8039"`, the UI check uses its own database `re_dev_08`.

## Story Goal

A sales agent prints a contract as one PDF where every block — the parties, the unit, the price,
the payment plan and the full schedule — is written in English on the left and in Arabic on the
right, side by side on the same page, the way Egyptian sale contracts are laid out. The Arabic
side is right-to-left with joined letters (Noto Naskh Arabic), amounts read `8,580,000 EGP`, and a
long customer name wraps instead of being cut. **[US-07](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "US-07: As a sales agent, I want to print the contract with Arabic and English side by side, so that the customer signs one document they can read.")**, **[BR-38](../../../../docs/business-requirements.md#collections-documents-and-data "BR-38: The contract prints as one PDF with Arabic and English side by side: parties, unit, price, plan, and the full schedule table.")**.

This is one QWeb report with two columns, not Odoo's translation system: the Arabic words are
fixed labels in the template, and the data (names, codes, amounts, dates) is printed on both sides
as stored.

Not in this story: legal clauses or contract wording beyond the data in BR-38; e-signature; an
Arabic translation of the UI (`i18n/ar.po`); Story 04 fields (invoice or payment state per line) —
the PDF prints Story 03's schedule lines only.

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/08-bilingual-pdf/intake.md` — the ACs below, the font risk and
  its fallback (English PDF ships, Arabic becomes a follow-up).
- `docs/business-requirements.md` — [US-07](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "US-07: As a sales agent, I want to print the contract with Arabic and English side by side, so that the customer signs one document they can read."), [BR-38](../../../../docs/business-requirements.md#collections-documents-and-data "BR-38: The contract prints as one PDF with Arabic and English side by side: parties, unit, price, plan, and the full schedule table."); Ch. 3 glossary (the Arabic words: عقد ابتدائي, مقدم,
  قسط, وديعة صيانة, الرقم القومي, …); §6.6 Example A (the sample contract) and C (a 62-line
  schedule over several pages).
- `addons/real_estate_eg/models/real_estate_contract.py` — `partner_id`, `unit_id`, `project_id`,
  `user_id`, `date`, `price`, `currency_id`, `plan_id`, `installment_ids`, `schedule_total`.
- `addons/real_estate_eg/models/real_estate_installment.py` — `LINE_TYPE`, `number`, `name`,
  `amount`, `date_due` (empty for a deposit due at delivery).
- `addons/real_estate_eg/models/real_estate_plan_template.py` — `FREQUENCY`, `maintenance_due`.
- `addons/real_estate_eg/models/real_estate_unit.py` — `code`, `unit_type`, `area`, `floor`.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon`, `create_contract()`,
  `generate_schedule()`, the §6.3 plans.
- `docker/docker-compose.ci.yml` — the pinned `odoo:19.0` image the CI tests run in.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/odoo/addons/base/models/ir_actions_report.py` — `ir.actions.report` fields
  `report_type` (`qweb-pdf`), `report_name`, `report_file`, `paperformat_id`,
  `print_report_name`, `binding_model_id` / `binding_type`; `_render_qweb_html()` (returns
  `(html, 'html')`); `_render_qweb_pdf()` → `_pre_render_qweb_pdf()`, which **in a test run returns
  HTML instead of a PDF** unless the context has `force_report_rendering`;
  `_get_rendering_context()` → uses the model `report.<report_name>` and its
  `_get_report_values()` when it exists; `get_wkhtmltopdf_state()`; `_get_report_url()` (the
  `report.url` parameter, else the base URL: where wkhtmltopdf fetches the CSS from).
- `odoo-src/odoo/odoo/addons/base/models/report_paperformat.py` — `report.paperformat`: `format`
  (default A4), `orientation` (**default Landscape**), margins, `header_spacing`, `dpi`.
- `odoo-src/odoo/addons/sale/report/ir_actions_report.xml` — `action_report_saleorder`: the shape
  of a report action bound to the Print menu.
- `odoo-src/odoo/addons/l10n_sa/data/report_paperformat_data.xml` — a module's own paper format
  record.
- `odoo-src/odoo/addons/web/views/report_templates.xml` — `web.html_container`,
  `web.external_layout` (company header and footer), `web.basic_layout`; `web.report_layout` sets
  `<body dir>` from the user's language, so the Arabic side must set its own `dir="rtl"`.
- `odoo-src/odoo/addons/account/report/account_invoice_report.py` —
  `report.account.report_invoice` (`models.AbstractModel`, `_get_report_values()`): the shape of
  our report model.
- `odoo-src/odoo/addons/account/__manifest__.py` — adds `report_invoice.css` to the
  `web.report_assets_common` bundle: the shape of our report CSS.
- `odoo-src/odoo/odoo/addons/base/models/ir_qweb_fields.py` — `ir.qweb.field.monetary`
  (`display_currency`, `decimal_places`; prints the currency **symbol**, `LE` for EGP, see
  `base/data/res_currency_data.xml`) and `ir.qweb.field.float` (`precision`; `lang.format(...,
  grouping=True)` gives the thousands separators).
- `odoo-src/odoo/addons/account/tests/test_early_payment_discount.py` —
  `with_context(force_report_rendering=True)._render_qweb_pdf(...)` in a test: a real PDF.

## Implementation tasks

Small steps, in order: what and why with its US / BR / AC → the code, each block commented with
the rule it implements → tests in the same step → `make test` (isolated database) → **one commit
per step**. At the maintainer's request (2026-11-25), the steps run one after another without a
stop in between; the review is per commit and at the PR.

Files are new unless marked *(edit)*. All under `addons/real_estate_eg/` unless a path says
otherwise.

**Step 0 — Branch and plan commit.** Branch `story/08-bilingual-pdf` from `origin/main`
(`89908b9`); commit this plan and the overview row.

**Step 1 — Arabic font in the CI image** (`docker/Dockerfile.ci`, `docker/docker-compose.ci.yml`
*(edit)*, `README.md` *(edit)*). *S08.1.*
1. `docker/Dockerfile.ci`: `FROM` the same pinned `odoo:19.0` digest; as `root`, `apt-get install
   --no-install-recommends fonts-noto-core` (Noto Naskh Arabic), clean the apt lists; back to user
   `odoo`.
2. Compose: the `odoo` service builds that file instead of pulling the image directly (digest
   stays pinned in the `FROM`).
3. README *Requirements*: the font package and the `fc-list` check.
*Check:* `docker compose -f docker/docker-compose.ci.yml build` and `fc-list` inside it shows Noto
Naskh Arabic; `make test-ci` still green.

**Step 2 — Report skeleton** (`report/real_estate_contract_report.xml`,
`report/real_estate_contract_templates.xml`, `static/src/css/contract_report.css`,
`__manifest__.py` *(edit)*: `data` + `assets`). *[US-07](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "US-07: As a sales agent, I want to print the contract with Arabic and English side by side, so that the customer signs one document they can read."), [BR-38](../../../../docs/business-requirements.md#collections-documents-and-data "BR-38: The contract prints as one PDF with Arabic and English side by side: parties, unit, price, plan, and the full schedule table.").*
1. `report.paperformat` `paperformat_contract`: A4, **Portrait** (the model's default is
   Landscape), margins for the company header.
2. `ir.actions.report` `action_report_contract`: "Contract (Arabic / English)", model
   `real.estate.contract`, `qweb-pdf`, `report_name` / `report_file`
   `real_estate_eg.report_contract`, `print_report_name` `'Contract - %s' % object.name`, bound
   to the contract's Print menu, the paper format above.
3. Templates: `report_contract` loops over `docs` inside `web.html_container`;
   `report_contract_document` calls `web.external_layout` and holds a two-column table (English
   cell left, Arabic cell right with `dir="rtl"` and class `o_re_ar`); a title row
   "Preliminary Sale Contract" / "عقد بيع ابتدائي", the reference and the contract date.
4. CSS in `web.report_assets_common` (as `account` does): `.o_re_ar` uses `"Noto Naskh Arabic"`;
   both columns 50 % with `table-layout: fixed`; long words wrap (`overflow-wrap`).
*Check:* `make test`; on `re_dev_08`, Print → "Contract (Arabic / English)" downloads a PDF.

**Step 3 — Parties, unit, price, plan** (`report/__init__.py`,
`report/real_estate_contract_report.py`, `__init__.py` *(edit)*, templates *(edit)*,
`tests/test_report.py`, `tests/__init__.py` *(edit)*). *[BR-38](../../../../docs/business-requirements.md#collections-documents-and-data "BR-38: The contract prints as one PDF with Arabic and English side by side: parties, unit, price, plan, and the full schedule table."), [AC-07.1](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.1: The rendered report contains the Arabic and English text for parties, unit, price, plan and every schedule line, with the Arabic side marked right-to-left (dir=&quot;rtl&quot;). (manual: letters joined, columns side by side in the PDF.)"), [AC-07.2](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.2: A 60-character customer name appears in full in the rendered report. (manual: the layout does not break.)"),
[AC-07.3](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.3: Amounts show with thousands separators and the currency, e.g. 8,580,000 EGP.").*
1. Report model `report.real_estate_eg.report_contract` (`models.AbstractModel`,
   `_get_report_values()`): returns the contracts plus the Arabic labels for the selection values
   (unit type, frequency, line type, deposit due) — one dictionary, so the template has no
   hard-coded `if` chains and a missing label is caught by a test.
2. Rows, each English | Arabic: Seller (company) / البائع; Buyer (name, national ID or passport)
   / المشتري; Sales agent / مندوب المبيعات; Unit (code, project, type, area, floor) / الوحدة;
   Contract price / سعر الوحدة; Payment plan (name, code, down payment %, installments,
   frequency, deposit % and when due) / نظام السداد.
3. Amounts: the `float` widget with `precision` 0 (thousands separators from the language) plus
   the currency code → `8,580,000 EGP`. On the Arabic side the amount sits in `<span
   dir="ltr">`, so it does not flip to `EGP 8,580,000`.
4. T1 (parties to plan), T2, T3 (price). *Check:* `make test`.

**Step 4 — The full schedule table** (templates *(edit)*, CSS *(edit)*, `tests/test_report.py`
*(edit)*). *[BR-38](../../../../docs/business-requirements.md#collections-documents-and-data "BR-38: The contract prints as one PDF with Arabic and English side by side: parties, unit, price, plan, and the full schedule table."), [AC-07.1](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.1: The rendered report contains the Arabic and English text for parties, unit, price, plan and every schedule line, with the Arabic side marked right-to-left (dir=&quot;rtl&quot;). (manual: letters joined, columns side by side in the PDF.)"), [AC-07.3](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.3: Amounts show with thousands separators and the currency, e.g. 8,580,000 EGP.").*
1. One table, one row per schedule line: #, description in English ("Installment 3") and Arabic
   ("القسط 3") side by side, due date, amount. The deposit due at delivery has no date: "On
   delivery" / "عند الاستلام". A total row (down payment + installments = the price), and the
   deposit shown apart, as [BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date.") says.
2. Long schedules (Example C: 62 lines) run over pages: the header row repeats (`thead`) and a row
   is never split.
3. No schedule yet (a draft): one line "No schedule generated yet" / "لم يتم إنشاء جدول السداد
   بعد" instead of an empty table.
4. A draft prints with a "Draft" / "مسودة" mark, so an unconfirmed contract is not signed by
   mistake.
5. T1 (every line), T3 (line amounts), T5. *Check:* `make test`.

**Step 5 — The real PDF and its font** (`tests/test_report.py` *(edit)*). *S08.1,
[AC-07.1](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.1: The rendered report contains the Arabic and English text for parties, unit, price, plan and every schedule line, with the Arabic side marked right-to-left (dir=&quot;rtl&quot;). (manual: letters joined, columns side by side in the PDF.)") (manual part).*
1. T4: render a real PDF (`force_report_rendering`) and check that Noto Naskh Arabic is embedded
   in it. If the CSS is not reached in the test run (wkhtmltopdf fetches it from `report.url` or
   the base URL, and tests run on another port), the test sets `report.url` to the test server.
2. On `re_dev_08`: Example A (and C) generated, PDF printed, rendered to an image and attached
   for the maintainer's manual check — joined letters, columns side by side, 60-character name.
*Check:* `make test`; `make test-ci` (T4 runs against the new CI image).

**Step 6 — Gates.** `make test`, `make lint`, `make test-ci`; log clean.

**Step 7 — Docs + PR.** `docs/design-notes/08-bilingual-pdf.md` (two columns vs translation,
the font and wkhtmltopdf, bidi of amounts, test-mode HTML vs real PDF, negative checks; 3
explain-back questions); `docs/learning-log.md` mistake rows; `README.md` *(edit)*: roadmap 08 →
in review. Done Criteria ticked in `plan.md` and `plan.ar.md`. PR; CI green; the maintainer
answers the explain-back questions in `docs/learning-log.md` and merges with "Create a merge
commit" (rebased on `main` first if Story 04 merged before).

## Edge Cases & Failure Modes

1. **Disconnected Arabic letters.** wkhtmltopdf shapes Arabic only with a font that has the
   joining forms; without one the letters print apart (or as boxes). Noto Naskh Arabic is named
   in the CSS and installed in both places; T4 proves it is embedded, the eye checks the joining.
   Fallback from the intake: if it cannot be made to work, the English PDF ships and Arabic
   becomes a follow-up, written in the README.
2. **Amount flips in the Arabic column.** `8,580,000 EGP` inside a right-to-left paragraph is
   shown as `EGP 8,580,000` by the bidi algorithm. Wrapped in `dir="ltr"`.
3. **Digits.** Both sides use Western digits (`8,580,000`), as Egyptian developers' printed
   schedules do; one number, no conversion to Eastern Arabic digits (٨٬٥٨٠٬٠٠٠). A choice for the
   maintainer to confirm.
4. **Currency symbol.** The `monetary` widget prints the symbol `LE` and two decimals
   (`8,580,000.00 LE`); AC-07.3 wants whole pounds and the code `EGP`. Hence the `float` widget
   with precision 0 and `currency_id.name`.
5. **Long names.** A 60-character customer name (AC-07.2) or a long project name wraps inside its
   column (`table-layout: fixed`, `overflow-wrap`); it is never cut and never pushes the Arabic
   column off the page.
6. **Paper format default.** `report.paperformat` defaults to Landscape; the record sets Portrait.
7. **Test mode renders HTML.** In a test run `_render_qweb_pdf()` returns HTML unless
   `force_report_rendering` is set, so T1–T3, T5 check HTML and only T4 makes a real PDF.
8. **wkhtmltopdf missing or broken** (`get_wkhtmltopdf_state()` ≠ `ok`): T4 is skipped with a
   message instead of failing; both local and CI have it, so a skip there is investigated.
9. **Deposit with no date** (due at delivery, [BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date.")): printed as "On delivery" / "عند
   الاستلام", not an empty cell.
10. **Draft or no schedule.** A draft prints with a "Draft" / "مسودة" mark; no schedule prints a
    one-line message (Step 4).
11. **Data in one script.** Names, codes and the company name are stored once; both columns
    print them as typed. Only the labels are translated. An Arabic company name or customer name
    field is out of scope.
12. **Who can print.** Whoever can read the contract (agent, manager, collections, accountant);
    the report has no group of its own. Story 06's record rules will limit agents to their own
    contracts, and the report follows them, as it renders with the user's rights.
13. **Story 04 in parallel.** No Story 04 field is printed; conflicts only in shared files,
    solved at rebase.

## Test Plan

Tests in `addons/real_estate_eg/tests/test_report.py`, `@tagged("post_install", "-at_install")`,
on `RealEstateCommon`. The report is rendered `with_user()` the agent (or the read-only roles in
T5), never as admin. HTML is parsed with `lxml` so "on the Arabic side" means "inside an element
with `dir="rtl"`".

| # | Test | Proves |
|---|---|---|
| T1 | `test_ac_07_1_bilingual_side_by_side` (Example A, 34 lines: every English label outside and every Arabic label inside a `dir="rtl"` element, for parties, unit, price, plan and each schedule line; one row per line) | [AC-07.1](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.1: The rendered report contains the Arabic and English text for parties, unit, price, plan and every schedule line, with the Arabic side marked right-to-left (dir=&quot;rtl&quot;). (manual: letters joined, columns side by side in the PDF.)"), [BR-38](../../../../docs/business-requirements.md#collections-documents-and-data "BR-38: The contract prints as one PDF with Arabic and English side by side: parties, unit, price, plan, and the full schedule table.") |
| T2 | `test_ac_07_2_long_customer_name` (a 60-character name appears in full on both sides) | [AC-07.2](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.2: A 60-character customer name appears in full in the rendered report. (manual: the layout does not break.)") |
| T3 | `test_ac_07_3_amount_format` (`8,580,000 EGP`, `858,000 EGP`, `241,313 EGP`, `241,297 EGP`, `686,400 EGP`; no `LE`, no `.00`; Arabic-side amounts inside `dir="ltr"`) | [AC-07.3](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.3: Amounts show with thousands separators and the currency, e.g. 8,580,000 EGP.") |
| T4 | `test_s08_1_arabic_font_embedded` (real PDF with `force_report_rendering`; Noto Naskh Arabic embedded) | S08.1 |
| T5 | `test_print_draft_and_read_only_roles` (draft without schedule: message on both sides + draft mark; collections officer and accountant can print) | edges 10, 12 |
| T6 | `make test`, `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Manual checks** (attached to the PR as a rendered page): Arabic letters joined; the two columns
side by side; the 60-character name wraps without breaking the layout; a 62-line schedule over
pages with the header repeated.

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: drop `dir="rtl"` from the Arabic cells → T1 fails.
- N2: print amounts with the `monetary` widget → T3 fails (`LE`, `.00`).
- N3: remove the font from the CSS → T4 fails.
- N4: remove one Arabic line-type label from the report model → T1 fails.

## Verification Steps

```bash
make test TEST_DB=re_test_08 ARGS="--http-port 8039"   # T1–T5 pass, log clean
make lint                                              # pre-commit green
make test-ci                                           # same tests in the CI image with the font
make run DB=re_dev_08 ARGS="--http-port 8039 -i real_estate_eg"   # print Example A, look at it
gh pr checks                                           # pre-commit + test green on the PR
gh run list --branch main --limit 1                    # green after merge
```

## Done Criteria

- [ ] **[AC-07.1](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.1: The rendered report contains the Arabic and English text for parties, unit, price, plan and every schedule line, with the Arabic side marked right-to-left (dir=&quot;rtl&quot;). (manual: letters joined, columns side by side in the PDF.)")** The printed contract has English and Arabic side by side for the parties,
  unit, price, plan and every schedule line, the Arabic side marked `dir="rtl"`. *Proof:* T1;
  manual: letters joined, columns side by side in the PDF.
- [ ] **[AC-07.2](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.2: A 60-character customer name appears in full in the rendered report. (manual: the layout does not break.)")** A 60-character customer name appears in full. *Proof:* T2; manual: the
  layout does not break.
- [ ] **[AC-07.3](../../../../docs/business-requirements.md#us-07--print-the-contract-in-arabic-and-english "AC-07.3: Amounts show with thousands separators and the currency, e.g. 8,580,000 EGP.")** Amounts show with thousands separators and the currency, e.g.
  `8,580,000 EGP`. *Proof:* T3.
- [ ] **S08.1** An Arabic font (Noto Naskh Arabic) is installed locally and in the CI image, and
  the setup is written in the README. *Proof:* T4 (in `make test` and in CI), Step 1 check,
  README.
