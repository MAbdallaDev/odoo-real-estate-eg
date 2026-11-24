# 03 — Payment plan templates and the schedule generator

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/03-schedule-generator/intake.md`
- **Branch:** `story/03-schedule-generator`
- **Status:** Done Criteria approved 2026-11-23; in progress

---

## Prerequisites

- Story 02 merged (PR #2, merge commit `824c3a3`); CI green on `main`.
- Local `main` clean and in sync with `origin/main`.
- `make test`, `make lint` and `make test-ci` green on `main` before the branch is cut.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Nothing new to install: `python-dateutil` (`relativedelta`) is in Odoo's `requirements.txt`;
  `decimal` is in the standard library.
- **Before Step 1 updates `re_dev`:** two contacts there share national ID `29901158800017`. Clear
  it on the one that is not the real customer, or the new unique index cannot be built.

## Story Goal

A sales agent picks a payment plan template on a draft contract and generates its schedule: a down
payment, N installments at a monthly / quarterly / semi-annual / annual step, and a separate
maintenance deposit line. Amounts are whole EGP rounded half up, the last installment absorbs the
rounding difference, and every due date is computed from the contract date with month-end
clamping. The schedule can be regenerated only while the contract is draft; a manager cannot
confirm a contract without a schedule that sums to its price.

Also in this story (carried over from Story 02's review, agreed with the maintainer): a new rule,
**[BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.")** — a national ID or passport number belongs to one contact only, across all contacts.

**The maintainer writes the schedule arithmetic** (Step 5): amounts, half-up rounding, the
last-line adjustment and the due dates. Its tests are written first (Step 4), so they define
"correct" before the code exists. The AI writes everything around it.

Not in this story: invoicing lines and line payment states (Story 04); the maintenance deposit's
due date being filled on delivery (Story 04 — `action_deliver()`'s docstring already says so);
late fees (Story 05); record rules (Story 06); plan demo data for Nile Heights (Story 10 — tests
create the §6.3 plans themselves).

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/03-schedule-generator/intake.md` — the ACs below, §6.3 plan
  templates, Examples A, B and C.
- `docs/business-requirements.md` — [BR-14](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-14: A payment plan template defines: down payment %, number of installments, frequency (monthly, quarterly, semi-annual, annual), months from contract date to the first installment, maintenance deposit %, and when the maintenance deposit is due (at signing or at delivery).")…[BR-20](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-20: A plan with 0 installments and 100% down payment is valid (a cash sale)."), [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695)."), [BR-10](../../../../docs/business-requirements.md#contracts "BR-10: Only a sales manager can confirm a contract. Confirmation requires: a generated schedule whose down payment plus installments equal the contract price exactly, and the customer identity in BR-05."), [BR-05](../../../../docs/business-requirements.md#customers "BR-05: The customer is a contact (person or company). Each individual buyer has a nationality: Egyptian or foreign (a field on the contact — the address country does not say it). An Egyptian individual must have a national ID (الرقم القومي) before the contract can be confirmed; a foreign individual must have a passport number instead. A company buyer has no identity check in v1."),
  [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."); §5.3 *Schedule line states* (states come in Story 04); §6.6 Examples A–C.
- `docs/design-notes/02-core-models.md` — the two-layer [BR-04](../../../../docs/business-requirements.md#projects-and-units "BR-04: A unit can have at most one contract that is not cancelled. Creating a second one fails, whoever tries and in whatever order (the double-sale case). It is enforced in the database, so it holds even when two users save at the same moment.") (Python message + database
  index), reused for [BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.").
- `addons/real_estate_eg/models/real_estate_contract.py` — `write()` guard,
  `_confirmation_error_message()` (Story 02 left the schedule check for here), `action_deliver()`.
- `addons/real_estate_eg/models/res_partner.py` — `_check_national_id` ([BR-06](../../../../docs/business-requirements.md#customers "BR-06: A national ID is valid only if it has 14 digits, its first digit is 2 (born 1900–1999) or 3 (born 2000–2099), and digits 2–7 form a real date of birth (YYMMDD) that is not in the future.")).
- `addons/real_estate_eg/wizard/real_estate_contract_cancel.py` — the transient-wizard shape.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon` fixtures and `create_contract()`.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/odoo/addons/base/models/res_partner.py` — `_compute_same_vat_partner_id()`:
  Odoo itself only *warns* on a duplicate tax ID, and searches with
  `with_context(active_test=False).sudo()` so archived contacts and other companies count. [BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.")
  uses the same search but *blocks* the save.
- `odoo-src/odoo/odoo/orm/table_objects.py` — `models.UniqueIndex(definition, message)`, with a
  `WHERE` clause (as Story 02's `_unit_live_unique`).
- `odoo-src/odoo/addons/sale/models/sale_order.py` — `order_line = fields.One2many(...)` and
  `_compute_amounts()` with `@api.depends('order_line.price_subtotal', ...)`: the shape of
  `installment_ids` and the schedule total.
- `odoo-src/odoo/addons/sale/models/sale_order_line.py` — `order_id` with
  `ondelete='cascade', index=True`: the shape of `contract_id` on a schedule line.
- `odoo-src/odoo/addons/sale/wizard/sale_make_invoice_advance.py` — a transient wizard opened
  from a record (`sale.advance.payment.inv`, default from context).
- `odoo-src/odoo/addons/account/models/account_payment_term.py` — `_compute_terms()`: Odoo's own
  due-date / amount split. **Not used**: one schedule line per invoice ([BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line."), Q2 in Ch. 8)
  needs our own lines; read it only to compare.
- `odoo-src/odoo/odoo/addons/base/models/res_currency.py` — `compare_amounts()` for the
  "sums to the price" check.
- `odoo-src/odoo/odoo/tools/float_utils.py` — `float_round(..., rounding_method='HALF-UP')`,
  the Odoo alternative to `Decimal` allowed by [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).").
- `odoo-src/odoo/odoo/tools/date_utils.py` — imports `relativedelta` from `dateutil`; adding
  `relativedelta(months=n)` clamps to the month end (31 Jan + 1 month = 28 Feb).
- `odoo-src/odoo/odoo/tests/common.py` — `TransactionCase`, `new_test_user`;
  `odoo-src/odoo/odoo/tests/form.py` — `Form`, to drive the generate wizard like the UI.

## Implementation tasks

Small review steps, in order, as in Story 02: what and why with its US / BR / AC → the code, each
block commented with the rule it implements → the maintainer runs the check → review → **one
commit per step**. Tests are written in the same step as the code they prove, except Step 4, whose
tests come *before* the maintainer's code.

Files are new unless marked *(edit)*. All under `addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Branch and plan commit.** `git switch -c story/03-schedule-generator` from up-to-date
`main`; commit this plan and the overview row.

**Step 1 — One contact per national ID / passport** (`docs/business-requirements.md` *(edit)*,
intake *(edit)*, `models/res_partner.py` *(edit)*, `tests/test_partner.py` *(edit)*). *[BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact."),
[BR-05](../../../../docs/business-requirements.md#customers "BR-05: The customer is a contact (person or company). Each individual buyer has a nationality: Egyptian or foreign (a field on the contact — the address country does not say it). An Egyptian individual must have a national ID (الرقم القومي) before the contract can be confirmed; a foreign individual must have a passport number instead. A company buyer has no identity check in v1.").*
1. Write [BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.") in the Customers table of `docs/business-requirements.md` (and the local
   `.ar.md`), and in the intake's rule table.
2. Python check `_check_identity_free()`, called before `super()` in `create()` and `write()`
   (an `@api.constrains` runs after the INSERT, so the index would refuse first with no name):
   search with `with_context(active_test=False).sudo()` for another contact with the same
   number; raise `ValidationError` naming that contact.
3. Database: two `models.UniqueIndex` on `res.partner` — `(national_id) WHERE national_id IS NOT
   NULL AND national_id != ''`, same for `passport_number` — so two saves at the same moment still
   fail.
4. T1. *Check:* clean the `re_dev` duplicate, then `make test`; restart `re_dev` with `-u`.

**Step 2 — Plan templates** (`models/real_estate_plan_template.py`, `models/__init__.py`
*(edit)*, ACL rows, `views/real_estate_plan_template_views.xml`, menus *(edit)*,
`__manifest__.py` *(edit)*, `tests/test_plan_template.py`). *[BR-14](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-14: A payment plan template defines: down payment %, number of installments, frequency (monthly, quarterly, semi-annual, annual), months from contract date to the first installment, maintenance deposit %, and when the maintenance deposit is due (at signing or at delivery)."), [BR-20](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-20: A plan with 0 installments and 100% down payment is valid (a cash sale).").*
1. `real.estate.plan.template` — `name`, `code`, `down_payment_percent`, `installment_count`,
   `frequency` (Selection monthly / quarterly / semi_annual / annual), `first_installment_months`,
   `maintenance_percent`, `maintenance_due` (Selection signing / delivery), `company_id`
   (default current company), `active`. A module constant maps frequency → step months
   (1 / 3 / 6 / 12).
2. `models.Constraint`: UNIQUE (company_id, code); both percentages 0–100; counts and months ≥ 0.
   `@api.constrains`: 0 installments ⇔ 100% down payment ([BR-20](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-20: A plan with 0 installments and 100% down payment is valid (a cash sale)."): the cash plan is the only
   0-installment plan; 100% down with installments would make 0-amount lines).
3. ACL: manager RWCD; agent, collections and `account.group_account_invoice` read.
4. List, form, search views; menu Configuration → Payment Plans (manager).
5. T2, T3. *Check:* `make test`; create `NH-STD-8Q` and `NH-CASH` on `re_dev`.

**Step 3 — Schedule lines on the contract** (`models/real_estate_installment.py`, contract model
*(edit)*, ACL rows, contract form *(edit)*). *[US-02](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "US-02: Generate the payment schedule from a plan"), [BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date."), [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked."), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.").*
1. `real.estate.installment` — `contract_id` (required, `ondelete='cascade'`, indexed),
   `sequence`, `line_type` (Selection down_payment / installment / maintenance), `number` (k for
   installments), `name` (computed label, e.g. "Installment 3"), `amount` (Monetary),
   `date_due` (empty for a deposit due at delivery), `company_id` and `currency_id` from the
   contract. `_order = 'contract_id, sequence, id'`.
2. [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.") lock: `create()`, `write()` and `@api.ondelete` refuse a change to a line whose
   contract is not draft — for everyone, managers too; only the superuser (Story 04's nightly job)
   passes.
3. Contract: `plan_id` (Many2one, `check_company=True`, tracked, read-only on the form — set by
   the wizard), `installment_ids` (One2many, `copy=False`), `schedule_total` (computed: down
   payment + installments, the deposit excluded per [BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date.")).
4. ACL: agent RWCD (draft only, by the lock), manager RWCD, collections R,
   `account.group_account_invoice` R.
5. Contract form: a "Schedule" page with the lines (read-only list) and the total.
6. T16 (lock and total), with lines made by hand until the generator exists.
*Check:* `make test` (Story 02 tests still green); the page shows on `re_dev`.

**Step 4 — Arithmetic tests first** (`tools/__init__.py`, `tools/schedule.py` — signature and
docstring only, body `raise NotImplementedError`; `tests/test_schedule_math.py`). *[BR-15](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-15: Down payment = contract price × down payment %, rounded to whole EGP (half up). Due on the contract date."),
[BR-16](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-16: Installments: (contract price − down payment) ÷ number of installments, each rounded to whole EGP (half up). The last installment absorbs the rounding difference, so down payment + installments = contract price to the pound."), [BR-17](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-17: Due dates are always computed from the contract date — installment k is due offset + (k−1) × step months after it — never from the previous due date. A date past the end of a short month moves to that month's last day, without drift: a plan anchored on 31 January falls due on 28 Feb, 31 Mar, 30 Apr, 31 May."), [BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date."), [BR-20](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-20: A plan with 0 installments and 100% down payment is valid (a cash sale)."), [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695)."), [AC-02.1](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.1: Given a contract at 8,580,000 on 10 Jan 2027 with plan NH-STD-8Q, when the agent generates the schedule, then there is a down payment of 858,000 due 10 Jan 2027, 31 installments of 241,313 and a last installment of 241,297, quarterly from 10 Apr 2027 to 10 Jan 2035, and a maintenance deposit of 686,400 with no due date (due at delivery).")…[AC-02.4](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.4: Given plan NH-CASH, the schedule is one down payment of the full price and no installments.").*
1. The function the maintainer will write, as a pure function (no ORM, so it is tested in
   isolation):
   ```python
   def compute_schedule(
       price,                     # contract price, whole EGP
       contract_date,             # datetime.date
       down_payment_percent,      # 10 means 10 %
       installment_count,         # N; 0 for a cash plan
       step_months,               # 1, 3, 6 or 12
       first_installment_months,  # months from the contract date to installment 1
       maintenance_percent,       # 8 means 8 %
       maintenance_at_signing,    # True: due on the contract date; False: no date yet
   ):
       """Return a list of dicts, in order: the down payment, installments 1..N,
       the maintenance deposit. Keys: line_type ("down_payment" | "installment" |
       "maintenance"), number (k for installments, 0 otherwise), amount (int, whole
       EGP), date_due (datetime.date or None). A down payment or deposit of 0 is
       left out."""
   ```
2. T4–T8, all red (`NotImplementedError`). *Check:* `make test` shows exactly these failing.

**Step 5 — ✋ The maintainer writes `compute_schedule()`** (`tools/schedule.py` *(edit)*).
*[BR-15](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-15: Down payment = contract price × down payment %, rounded to whole EGP (half up). Due on the contract date.")–[BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date."), [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).").* Exact decimal arithmetic, half up to whole EGP, the remainder
on the last installment, every date = contract date + (offset + (k−1) × step) months. The AI gives
hints only when asked. *Check:* T4–T8 green; then the AI reviews the code (and runs negative
checks N1, N2).
*As done (2026-11-24):* at the maintainer's choice the AI gave a skeleton (imports, loop, line
dicts, the `relativedelta` call); the maintainer wrote the six arithmetic lines (half up, down
payment, installment, last-line remainder, months for installment k, deposit). N1 and N2 seen
failing.

**Step 6 — Generate wizard** (contract model *(edit)*, `wizard/real_estate_schedule_generate.py`,
`wizard/real_estate_schedule_generate_views.xml`, `wizard/__init__.py`, ACL row, contract form
*(edit)*, `__manifest__.py` *(edit)*, `tests/test_schedule.py`). *[US-02](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "US-02: Generate the payment schedule from a plan"), [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked."),
[AC-02.1](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.1: Given a contract at 8,580,000 on 10 Jan 2027 with plan NH-STD-8Q, when the agent generates the schedule, then there is a down payment of 858,000 due 10 Jan 2027, 31 installments of 241,313 and a last installment of 241,297, quarterly from 10 Apr 2027 to 10 Jan 2035, and a maintenance deposit of 686,400 with no due date (due at delivery)."), [AC-02.4](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.4: Given plan NH-CASH, the schedule is one down payment of the full price and no installments."), [AC-02.5](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.5: Given a draft contract with a schedule, when the agent regenerates it with another plan, then the old lines are replaced. Given a confirmed contract, regeneration is refused.").*
1. Contract `_generate_schedule(plan)`: draft only, else `UserError` ([BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.")); contract date
   required; deletes the old lines, calls `compute_schedule()` with the plan's values, creates the
   lines, sets `plan_id`. Refuses a plan of 1+ installments that gives a line ≤ 0 (only possible
   with a tiny price).
2. Wizard `real.estate.schedule.generate` (transient): `contract_id`, `plan_id` (required,
   default the contract's plan); `action_generate()`. ACL: agent (managers imply agent).
3. "Generate Schedule" button on draft contracts, group agent.
4. A stale schedule is dropped: changing the unit (so the price) or the contract date of a draft
   that has lines deletes them, so it must be generated again.
5. `common.py` gets the §6.3 plan fixtures and a `generate_schedule()` helper that drives the
   dialog with `Form`. T9–T12, T17.
*Check:* `make test`; generate Example A on `re_dev` and read the lines.

**Step 7 — Confirmation needs the schedule** (contract model *(edit)*, `tests/common.py`
*(edit)*, Story 02 state tests *(edit)*). *[BR-10](../../../../docs/business-requirements.md#contracts "BR-10: Only a sales manager can confirm a contract. Confirmation requires: a generated schedule whose down payment plus installments equal the contract price exactly, and the customer identity in BR-05."), [AC-10.2](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.2: Confirmation is refused if there is no schedule, if the schedule does not sum to the price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A company customer needs neither.") (schedule part).*
1. `_confirmation_error_message()`: no lines → "Generate the schedule first"; `schedule_total`
   ≠ price (`currency_id.compare_amounts`) → refused with both amounts.
2. Story 02 tests that confirm a contract generate a schedule first, with a new `common.py`
   helper `add_schedule()`. The check runs last, so a wrong date or identity is reported first.
3. T13. Negative check N3. *Check:* `make test`.

**Step 8 — Read-only roles see the schedule** (`tests/test_access.py` *(edit)*). *[BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."),
[AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule."), [AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.") (schedule parts left from Story 02).* T14: collections and accountant
read lines and plans, but cannot edit a line, a plan or run the wizard;
`action_generate_schedule()` calls `check_access("write")`, so they are refused at the button.
Negative check N8. *Check:* `make test`.

**Step 9 — Whole flow + CI stack.** On `re_dev`: create the §6.3 plans, Example A and C contracts,
generate, regenerate with another plan, confirm as manager; log clean. Then `make lint`,
`make test-ci`.

**Step 10 — Docs + PR.** `docs/design-notes/03-schedule-generator.md` (pure function vs ORM,
`Decimal` half up vs `round()`, dates from the anchor, why lines and not payment terms, [BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.")
two layers, negative checks; 3 explain-back questions); `docs/learning-log.md` mistakes rows;
`README.md` *(edit)*: roadmap 02 → done, 03 → in review. Done Criteria ticked in `plan.md` and
`plan.ar.md`. PR; CI green; the maintainer merges with "Create a merge commit"; explain-back
answers in `docs/learning-log.md`.

## Edge Cases & Failure Modes

1. **Banker's rounding.** Python's `round(858000.5)` gives 858,000 (round half to even); [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).")
   wants 858,001 (price 8,580,005 at 10 %). T8 has this tie.
2. **Binary float.** In float, `1310730 * 0.35` is `458755.49999999994`, so even a hand-made "half
   up" on floats gives 458,755 instead of 458,756. `Decimal(str(value))` (or
   `float_round(..., rounding_method='HALF-UP')`) avoids it. T8 has this case too.
3. **Date drift.** Chaining from the previous due date gives 31 Jan → 28 Feb → **28** Mar.
   Always add from the contract date ([BR-17](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-17: Due dates are always computed from the contract date — installment k is due offset + (k−1) × step months after it — never from the previous due date. A date past the end of a short month moves to that month's last day, without drift: a plan anchored on 31 January falls due on 28 Feb, 31 Mar, 30 Apr, 31 May.")); T6 checks 31 Mar, 30 Apr, 31 May.
4. **Last line can go wrong.** With a tiny price and many installments the rounded-up lines can
   leave the last one ≤ 0. The generator refuses it; real prices never get near it.
5. **Cash plan** ([BR-20](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-20: A plan with 0 installments and 100% down payment is valid (a cash sale).")): 0 installments, 100 % down → one down payment line (+ the deposit).
   A 0-installment plan with less than 100 % down is refused at the template.
6. **Deposit not in the price** ([BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date.")): `schedule_total` excludes it, so the [BR-10](../../../../docs/business-requirements.md#contracts "BR-10: Only a sales manager can confirm a contract. Confirmation requires: a generated schedule whose down payment plus installments equal the contract price exactly, and the customer identity in BR-05.") check
   compares only down payment + installments with the price.
7. **Stale schedule.** Unit (price) or date changed on a draft → lines deleted; confirmation then
   asks for a new schedule. No silent mismatch.
8. **Empty contract date.** Generation refuses it — dates come from it ([BR-17](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-17: Due dates are always computed from the contract date — installment k is due offset + (k−1) × step months after it — never from the previous due date. A date past the end of a short month moves to that month's last day, without drift: a plan anchored on 31 January falls due on 28 Feb, 31 Mar, 30 Apr, 31 May.")).
9. **Locked after confirmation** ([BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.")): regeneration and any line create / write / delete
   refused, managers included; only the superuser passes (Story 04's job will write invoice links).
10. **Plan from another company** — `check_company=True` on `plan_id` refuses it.
11. **Collections officer** has no write ACL on lines or plans and no wizard ACL ([AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule.")).
12. **[BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.") hidden duplicates.** Without `sudo()` and `active_test=False`, a contact in
    another company or archived would be missed. The message names the contact (agreed: the
    agent needs to find the existing customer).
13. **[BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.") race.** Two saves at once both pass the Python check; the unique index stops the
    second. Empty strings are excluded from the index.
14. **Existing duplicates** in a database block the index on update — hence the `re_dev`
    clean-up in the prerequisites.
15. **Log check.** A missing ACL on a new model or wizard logs a warning and fails `make test`.
16. **[BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date.") empty date vs [BR-17](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-17: Due dates are always computed from the contract date — installment k is due offset + (k−1) × step months after it — never from the previous due date. A date past the end of a short month moves to that month's last day, without drift: a plan anchored on 31 January falls due on 28 Feb, 31 Mar, 30 Apr, 31 May.").** Generation needs a contract date, and confirmation needs a
    schedule, so in practice the date is always set before confirming; BR-07's "empty date becomes
    the confirmation date" is reached only by lines made outside the generator (T16 checks it).
17. **Contract date after confirmation.** The form already made it read-only, but Story 02's
    `write()` let a manager change it through an import or the API, so a confirmed schedule's dates
    could drift from it. Decided 2026-11-24 (maintainer): `write()` refuses a new date on a contract
    that is not draft, for everyone but the superuser, as for the unit ([BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date."), [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.")).
    `test_br_35_agent_edits_only_drafts` checks it; negative check N7.

## Test Plan

Tests under `addons/real_estate_eg/tests/`, all `@tagged("post_install", "-at_install")`. Plan
fixtures from §6.3 (`NH-STD-8Q`, `NH-BIZ-5M`, `NH-CASH`) are created in the tests; every action
runs `with_user()` an agent, manager, collections or Invoicing user.

| # | Test | Proves |
|---|---|---|
| T1 | `test_partner.py` — `test_br_46_identity_unique` (same national ID or passport refused with the other contact's name; across companies; archived contact counts; re-saving one's own number passes; database index blocks a raw duplicate) | [BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.") |
| T2 | `test_plan_template.py` — `test_br_14_plan_template_limits` (percent outside 0–100, negative counts, duplicate code refused) | [BR-14](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-14: A payment plan template defines: down payment %, number of installments, frequency (monthly, quarterly, semi-annual, annual), months from contract date to the first installment, maintenance deposit %, and when the maintenance deposit is due (at signing or at delivery).") |
| T3 | `test_plan_template.py` — `test_br_20_cash_plan` (0 installments + 100 % valid; 0 installments + 90 % refused) | [BR-20](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-20: A plan with 0 installments and 100% down payment is valid (a cash sale).") |
| T4 | `test_schedule_math.py` — `test_ac_02_1_example_a` (34 lines: amounts and every date) | [AC-02.1](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.1: Given a contract at 8,580,000 on 10 Jan 2027 with plan NH-STD-8Q, when the agent generates the schedule, then there is a down payment of 858,000 due 10 Jan 2027, 31 installments of 241,313 and a last installment of 241,297, quarterly from 10 Apr 2027 to 10 Jan 2035, and a maintenance deposit of 686,400 with no due date (due at delivery).") |
| T5 | `test_schedule_math.py` — `test_ac_02_2_example_b_sums_to_price` (+ a loop over several prices and plans) | [AC-02.2](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.2: Given any price and plan, down payment + installments = the contract price exactly. Tested with 6,712,345 on NH-STD-8Q: down payment 671,235, 31 × 188,785, last 188,775.") |
| T6 | `test_schedule_math.py` — `test_ac_02_3_example_c_month_end` (first four dates, installment 60 on 31 Jan 2032, deposit at signing) | [AC-02.3](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.3: Given plan NH-BIZ-5M on a contract dated 31 Jan 2027, the first four installments are due 28 Feb, 31 Mar, 30 Apr and 31 May 2027.") |
| T7 | `test_schedule_math.py` — `test_ac_02_4_cash_plan` | [AC-02.4](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.4: Given plan NH-CASH, the schedule is one down payment of the full price and no installments.") |
| T8 | `test_schedule_math.py` — `test_br_45_half_up_ties` (8,580,005 at 10 % → 858,001; 1,310,730 at 35 % → 458,756) | [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).") |
| T9 | `test_schedule.py` — `test_ac_02_1_generate_from_wizard` (agent, `Form`; lines stored, plan set, deposit has no date) | [AC-02.1](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.1: Given a contract at 8,580,000 on 10 Jan 2027 with plan NH-STD-8Q, when the agent generates the schedule, then there is a down payment of 858,000 due 10 Jan 2027, 31 installments of 241,313 and a last installment of 241,297, quarterly from 10 Apr 2027 to 10 Jan 2035, and a maintenance deposit of 686,400 with no due date (due at delivery).") |
| T10 | `test_schedule.py` — `test_ac_02_4_generate_cash_plan` | [AC-02.4](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.4: Given plan NH-CASH, the schedule is one down payment of the full price and no installments.") |
| T11 | `test_schedule.py` — `test_ac_02_5_regenerate_draft_only` (old lines replaced; confirmed → refused; line edit / delete refused, manager too) | [AC-02.5](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.5: Given a draft contract with a schedule, when the agent regenerates it with another plan, then the old lines are replaced. Given a confirmed contract, regeneration is refused."), [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.") |
| T12 | `test_schedule.py` — `test_stale_schedule_dropped` (unit or date change on a draft deletes the lines) | edge 7 |
| T13 | `test_contract_states.py` — `test_ac_10_2_schedule_required` (no schedule; a schedule not summing to the price; a full one passes) | [AC-10.2](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.2: Confirmation is refused if there is no schedule, if the schedule does not sum to the price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A company customer needs neither.") |
| T14 | `test_access.py` — `test_ac_06_3_collections_reads_cannot_edit`, `test_ac_06_5_accountant_reads_cannot_edit` *(edit)*: schedule lines, plans, wizard | [AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule."), [AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.") |
| T16 | `test_schedule.py` — `test_br_19_schedule_lines_locked` (lines made by hand: total leaves the deposit out; after confirmation agent and manager cannot create / write / delete a line; superuser can) | [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.") |
| T17 | `test_schedule.py` — `test_generate_refusals` (no contract date; 2,065 on `NH-BIZ-5M` leaves a last installment of 0) | edges 4, 8 |
| T15 | `make test`, `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: use Python `round()` instead of half up → T8 fails.
- N2: compute each date from the previous one → T6 fails.
- N3: remove the schedule check from confirmation → T13 fails.
- N5: skip the BR-19 lock → T16 fails.
- N6: skip the draft check in `_check_schedule_draft()` → T11 fails.
- N7: let a manager change the date of a confirmed contract → `test_br_35_agent_edits_only_drafts` fails.
- N8: give collections write on schedule lines in the CSV → T14 (collections) fails.
- N4: drop `sudo()` / `active_test=False` from the [BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.") search → T1 (other company / archived) fails.

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/03-schedule-generator
make test        # T1–T14, T16, T17 pass, log clean
make lint        # pre-commit green
make test-ci     # same tests in the CI Docker stack
make run ARGS="-u real_estate_eg"   # Step 9 walk-through on re_dev; log clean
gh pr checks     # pre-commit + test green on the PR
gh run list --branch main --limit 1   # green after merge
```

## Done Criteria

- [ ] **[AC-02.1](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.1: Given a contract at 8,580,000 on 10 Jan 2027 with plan NH-STD-8Q, when the agent generates the schedule, then there is a down payment of 858,000 due 10 Jan 2027, 31 installments of 241,313 and a last installment of 241,297, quarterly from 10 Apr 2027 to 10 Jan 2035, and a maintenance deposit of 686,400 with no due date (due at delivery).")** Contract at 8,580,000 dated 10 Jan 2027 on `NH-STD-8Q`: down payment
  858,000 due 10 Jan 2027; 31 installments of 241,313 and a last one of 241,297, quarterly from
  10 Apr 2027 to 10 Jan 2035; maintenance deposit 686,400 with no due date. *Proof:* T4, T9.
- [ ] **[AC-02.2](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.2: Given any price and plan, down payment + installments = the contract price exactly. Tested with 6,712,345 on NH-STD-8Q: down payment 671,235, 31 × 188,785, last 188,775.")** Down payment + installments = the contract price exactly; 6,712,345 on
  `NH-STD-8Q` gives 671,235, 31 × 188,785 and a last 188,775. *Proof:* T5.
- [ ] **[AC-02.3](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.3: Given plan NH-BIZ-5M on a contract dated 31 Jan 2027, the first four installments are due 28 Feb, 31 Mar, 30 Apr and 31 May 2027.")** `NH-BIZ-5M` on 31 Jan 2027: first four installments due 28 Feb, 31 Mar,
  30 Apr, 31 May 2027. *Proof:* T6.
- [ ] **[AC-02.4](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.4: Given plan NH-CASH, the schedule is one down payment of the full price and no installments.")** `NH-CASH`: one down payment of the full price, no installments.
  *Proof:* T7, T10.
- [ ] **[AC-02.5](../../../../docs/business-requirements.md#us-02--generate-the-payment-schedule-from-a-plan "AC-02.5: Given a draft contract with a schedule, when the agent regenerates it with another plan, then the old lines are replaced. Given a confirmed contract, regeneration is refused.")** Regenerating a draft's schedule with another plan replaces the old lines;
  on a confirmed contract it is refused. *Proof:* T11.
- [ ] **[AC-10.2](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.2: Confirmation is refused if there is no schedule, if the schedule does not sum to the price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A company customer needs neither.")** *(schedule part)* Confirmation is refused with no schedule or a schedule
  that does not sum to the price. *Proof:* T13.
- [ ] **[BR-46](../../../../docs/business-requirements.md#customers "BR-46: A national ID or passport number belongs to one contact only, across all contacts and all companies, archived contacts included. Saving a contact with a number another contact already has is refused, and the message names that contact.")** A national ID or passport number already on another contact (any company,
  archived included) is refused, and the message names that contact. *Proof:* T1.
