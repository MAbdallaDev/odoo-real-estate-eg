# 04 — Accounting link: invoices, payment state, closing and cancellation money

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/04-accounting-link/intake.md`
- **Branch:** `story/04-accounting-link`
- **Status:** all steps done 2026-11-25; Done Criteria met (52 tests green, test-ci green); in review

---

## Prerequisites

- Story 03 merged (PR #3, merge commit `89908b9`); CI green on `main`.
- Local `main` clean and in sync with `origin/main`.
- `make test`, `make lint` and `make test-ci` green on `main` before the branch is cut.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Nothing new to install: `freezegun` (to fix "today" in tests) is in Odoo's `requirements.txt`
  (1.2.1 in our venv) and in `debian/control` (`python3-freezegun`), so the CI image has it too.
- **For Step 10 on `re_dev`:** two liability accounts (customer advances, maintenance deposits)
  and an *Outstanding Receipts* account on the bank journal's incoming payment method. Step 10
  says how; nothing to do before.

## Story Goal

Every schedule line becomes **one posted customer invoice** — at confirmation for anything already
due, otherwise on its due date through a new **nightly job** — with no taxes, posted to a customer
advances account (the maintenance deposit to its own liability account). A line's state
(scheduled / invoiced / partly paid / paid / cancelled) and the contract's totals are **read from
accounting**, never typed. On delivery the maintenance deposit "due at delivery" gets its date and
is invoiced; a delivered contract whose lines are all paid closes on the next nightly run.
Cancelling a confirmed contract records the retention and refundable amount from real payments,
**then** credits whatever is invoiced but unpaid.

**ADR (recorded in this story):** `l10n_eg` is **not** a hard dependency. `depends` stays
`["account", "mail"]`; the two accounts are company settings, so the module works with any chart
of accounts. The README recommends `l10n_eg` for Egyptian companies.

Not in this story: late fees, overdue and at-risk flags (Story 05 adds those steps to the nightly
job); revenue recognition at delivery (v1.1); paying out the refund (the accountant's manual step,
[BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step.")); taxes and ETA e-invoicing; record rules (Story 06); demo data (Story 10).

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/04-accounting-link/intake.md` — the ACs below, §5.3 line states,
  §5.5 nightly job, Examples A, C, E.
- `docs/business-requirements.md` — [BR-12](../../../../docs/business-requirements.md#contracts "BR-12: A delivered contract closes automatically, on the next nightly run, when every line on it — down payment, installments, maintenance deposit and any billed late fees — is fully paid, and no accrued late fee is left unbilled. v1 has no late-fee waiver (Chapter 7)."), [BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date."), [BR-21](../../../../docs/business-requirements.md#invoicing-and-payment "BR-21: On confirmation, every line due on or before the confirmation date is invoiced at once — the down payment, a maintenance deposit due at signing, and any installment already due.")–[BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days)."), [BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step."),
  [BR-34](../../../../docs/business-requirements.md#cancellation "BR-34: On cancellation, whatever has been invoiced but not paid is credited: a fully unpaid invoice in full, a partly paid one by a credit note for exactly its unpaid remainder, reconciled with it. Lines not yet invoiced are cancelled, and the unit becomes available again. After cancellation every line shows cancelled — set by the module, not read from accounting, where a credited invoice shows as paid."), [BR-43](../../../../docs/business-requirements.md#invoicing-and-payment "BR-43: Down payment and installment invoices post to a configurable customer advances account, before and after delivery. v1 records no sales revenue; moving advances to revenue at delivery is v1.1 (Chapter 7)."), [BR-44](../../../../docs/business-requirements.md#invoicing-and-payment "BR-44: Schedule-line invoices carry no taxes in v1, even if the company has default sales taxes. Residential unit sales are VAT-exempt; the treatment of commercial units must be confirmed with a tax advisor."); §6.4 (retention 15 %, lead days 0, the two accounts).
- `docs/design-notes/03-schedule-generator.md` — the [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.") lock: only the superuser changes a
  line of a confirmed contract, which is how this story links invoices and dates the deposit.
- `addons/real_estate_eg/models/real_estate_contract.py` — `action_confirm()`, `action_deliver()`
  (its docstring leaves the deposit to this story), `_cancel_with_reason()` (leaves retention to
  this story), `_confirmation_error_message()`.
- `addons/real_estate_eg/models/real_estate_installment.py` — `_check_schedule_editable()` (passes
  for `env.su`), `LINE_TYPE`.
- `addons/real_estate_eg/tools/schedule.py` — `half_up()`, reused for the retention ([BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).")).
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon`, `add_schedule()`.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/addons/account/tests/common.py` — `AccountTestInvoicingCommon`: loads a chart of
  accounts into a fresh company (`setup_independent_company()` → `_create_company()` →
  `_use_chart_template()`), gives `company_data` (`default_journal_bank`, `default_tax_sale`, …),
  and sets the bank journal's inbound `payment_account_id` to *Outstanding Receipts*
  (`account_journal_payment_debit_account_id`). Helpers `_register_payment()` (the
  `account.payment.register` wizard) and `_reverse_invoice()`.
- `odoo-src/odoo/odoo/addons/base/tests/common.py` — `BaseCommon.setUpClass()`: switches `cls.env`
  to an independent user and company **after** `super().setUpClass()`; why our fixtures must be
  created after it.
- `odoo-src/odoo/addons/account/models/account_move.py` — `PAYMENT_STATE_SELECTION`
  (`not_paid`, `in_payment`, `paid`, `partial`, `reversed`, …); `amount_residual`;
  `_compute_payment_state()`; `_get_invoice_in_payment_state()` (returns `paid` in Community, so
  `in_payment` appears only with the Accountant app); `invoice_date_due` (stored compute,
  `readonly=False`; without a payment term `_compute_needed_terms()` keeps the value we set);
  `reversed_entry_id` / `reversal_move_ids`; `invoice_origin`; `action_post()`.
- `odoo-src/odoo/addons/account/models/account_payment.py` — `_generate_journal_entry()` only
  creates the payment's entry when `outstanding_account_id` is set (the [BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date.") trap);
  `_compute_outstanding_account_id()` takes it from `payment_method_line_id.payment_account_id`.
- `odoo-src/odoo/addons/account/models/account_move_line.py` — `_compute_tax_ids()` fills taxes
  from the product and account, so our lines pass `tax_ids` explicitly; `reconcile()`.
- `odoo-src/odoo/addons/account/tests/test_account_payment.py` — patches
  `_get_invoice_in_payment_state` with `patch.object(self.env.registry['account.move'], …)` to
  get `in_payment` in Community; T8 does the same.
- `odoo-src/odoo/addons/account/data/service_cron.xml` — `ir.cron` record shape
  (`model_id`, `state` `code`, `code`, `interval_type`, `user_id` `base.user_root`).
- `odoo-src/odoo/addons/account/views/res_config_settings_views.xml` — inherits
  `base.res_config_settings_view_form` with `<app>`, `<block>`, `<setting>`;
  `odoo-src/odoo/addons/account/models/res_config_settings.py` — `related="company_id.…"`
  settings fields.
- `odoo-src/odoo/odoo/orm/environments.py` — `uid == SUPERUSER_ID` sets `su = True`, so the cron
  (run as `base.user_root`) and `sudo()` both pass the [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.") lock.

## Implementation tasks

Small review steps, in order: what and why with its US / BR / AC → the code, each block commented
with the rule it implements → the maintainer runs the check → review → **one commit per step**.
Each step's Key points name the journal entry it creates (accounts, debit / credit).

Files are new unless marked *(edit)*. All under `addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Branch and plan commit.** `git switch -c story/04-accounting-link` from up-to-date
`main`; commit this plan and the overview row.

**Step 1 — Accounting settings, products, test base** (`models/res_company.py`,
`models/res_config_settings.py`, `models/__init__.py` *(edit)*, `views/res_config_settings_views.xml`,
`data/product_data.xml`, `__manifest__.py` *(edit)*, `tests/common.py` *(edit)*,
`tests/test_invoicing.py`). *[BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line."), [BR-23](../../../../docs/business-requirements.md#invoicing-and-payment "BR-23: The maintenance deposit is invoiced on its due date. It is money held for the compound's upkeep, not revenue, so it posts to a deposit liability account, never to sales revenue."), [BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step."), [BR-43](../../../../docs/business-requirements.md#invoicing-and-payment "BR-43: Down payment and installment invoices post to a configurable customer advances account, before and after delivery. v1 records no sales revenue; moving advances to revenue at delivery is v1.1 (Chapter 7)."), [BR-44](../../../../docs/business-requirements.md#invoicing-and-payment "BR-44: Schedule-line invoices carry no taxes in v1, even if the company has default sales taxes. Residential unit sales are VAT-exempt; the treatment of commercial units must be confirmed with a tax advisor.").*
1. `res.company`: `re_advance_account_id` and `re_maintenance_account_id` (Many2one
   `account.account`, liability types), `re_retention_percent` (default 15),
   `re_invoice_lead_days` (default 0). `res.config.settings`: the same as
   `related="company_id.…", readonly=False`; a "Real Estate" `<app>` block in Settings.
2. `data/product_data.xml`: three service products — Down Payment, Installment, Maintenance
   Deposit — with **no** customer taxes. (The late-fee product comes with Story 05.)
3. `RealEstateCommon` now inherits `AccountTestInvoicingCommon` (a chart of accounts, a bank
   journal with Outstanding Receipts) and creates the two liability accounts and sets them on the
   company. Fixtures stay after `super().setUpClass()`, so they live in the test company.
4. T1. *Check:* `make test` — the 37 Story 02/03 tests still green on the new base.

**Step 2 — One invoice per line** (`models/real_estate_installment.py` *(edit)*,
`tests/test_invoicing.py` *(edit)*). *[BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line."), [BR-23](../../../../docs/business-requirements.md#invoicing-and-payment "BR-23: The maintenance deposit is invoiced on its due date. It is money held for the compound's upkeep, not revenue, so it posts to a deposit liability account, never to sales revenue."), [BR-25](../../../../docs/business-requirements.md#invoicing-and-payment "BR-25: Each line invoices exactly once, however many times the invoicing job runs."), [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days)."), [BR-43](../../../../docs/business-requirements.md#invoicing-and-payment "BR-43: Down payment and installment invoices post to a configurable customer advances account, before and after delivery. v1 records no sales revenue; moving advances to revenue at delivery is v1.1 (Chapter 7)."),
[BR-44](../../../../docs/business-requirements.md#invoicing-and-payment "BR-44: Schedule-line invoices carry no taxes in v1, even if the company has default sales taxes. Residential unit sales are VAT-exempt; the treatment of commercial units must be confirmed with a tax advisor."), [AC-03.3](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.3: Given a maintenance deposit falls due, its invoice posts to the maintenance deposit liability account, not to sales revenue."), [AC-03.6](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.6: Given the company has a default sales tax, schedule-line invoices still carry no tax."), [AC-03.7](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.7: Down payment and installment invoices post to the customer advances account, not to sales revenue.").*
1. Line fields: `invoice_id` (Many2one `account.move`, read-only, `copy=False`,
   `groups="account.group_account_invoice"` — agents have no accounting rights), `invoice_date`
   (stored, from the invoice), `date_effective_due` (stored: the later of `date_due` and
   `invoice_date`, [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).")).
2. `_create_invoices(invoice_date)`: for each line **without** `invoice_id` ([BR-25](../../../../docs/business-requirements.md#invoicing-and-payment "BR-25: Each line invoices exactly once, however many times the invoicing job runs.")), one
   `out_invoice` per line in the contract's company: partner, `invoice_date`, `invoice_date_due` =
   effective due date, `invoice_origin` = contract reference; one line with the product for its
   type, `account_id` = advances (down payment, installment) or maintenance deposits (deposit),
   `price_unit` = amount, **`tax_ids` empty** ([BR-44](../../../../docs/business-requirements.md#invoicing-and-payment "BR-44: Schedule-line invoices carry no taxes in v1, even if the company has default sales taxes. Residential unit sales are VAT-exempt; the treatment of commercial units must be confirmed with a tax advisor.")); post it; write `invoice_id`. Runs with
   `sudo()`: managers and the cron have no accounting rights, and the line is locked ([BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.")).
3. A missing account → `UserError` naming the setting.
4. T2, T3, T4. *Check:* `make test`.

**Step 3 — Invoice at confirmation** (contract model *(edit)*, `tests/test_invoicing.py`
*(edit)*, Story 02/03 tests if needed). *[BR-21](../../../../docs/business-requirements.md#invoicing-and-payment "BR-21: On confirmation, every line due on or before the confirmation date is invoiced at once — the down payment, a maintenance deposit due at signing, and any installment already due."), [US-10](../../../../docs/business-requirements.md#us-10--confirm-a-contract "US-10: Confirm a contract"), [AC-03.1](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.1: When a contract is confirmed, then every line already due is invoiced immediately — the down payment, and for Example C (Chapter 6) also the maintenance deposit due at signing."), [AC-10.3](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.3: On confirmation the unit shows sold and every line already due is invoiced (BR-21).").*
1. `_invoice_due_lines(today)`: lines of confirmed or delivered contracts with a due date ≤ today
   \+ lead days and no invoice → `_create_invoices(today)`.
2. `action_confirm()` calls it after the state change: the down payment, a deposit due at
   signing, and any installment already due.
3. `_confirmation_error_message()`: refused while the company has no advances or maintenance
   account (a clear message, before anything is posted).
4. T5. *Check:* `make test`.

**Step 4 — Payment state and totals from accounting** (installment *(edit)*, contract *(edit)*,
contract form *(edit)*, `tests/test_payment_state.py`). *[BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date."), [AC-03.4](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.4: Given a 241,313 invoice and a bank journal with an outstanding receipts account, when a payment of 141,313 is registered, the line shows partly paid with 100,000 outstanding; when the rest is paid, it shows paid (also while accounting shows the invoice In payment)."), [AC-03.5](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.5: The contract shows total paid and total outstanding, both computed from accounting.").*
1. Line `state` (stored compute, §5.3): `cancelled` if the contract is cancelled; else
   `scheduled` with no invoice; `paid` when `payment_state` is `paid` or `in_payment`;
   `partially_paid` when `partial`; else `invoiced`. `amount_residual` (stored, from the
   invoice) and `amount_paid` (stored: invoice total − residual − credit notes in
   `reversal_move_ids`, so a credit note never counts as a payment).
2. Contract `amount_paid` and `amount_outstanding` (sum of the lines; outstanding = invoiced
   but unpaid).
3. Schedule list on the form: state badge, paid, outstanding; invoice column for accountants.
4. T8, T9. *Check:* `make test`.

**Step 5 — Nightly job: the invoicing step** (`data/ir_cron_data.xml`, `__manifest__.py`
*(edit)*, contract *(edit)*, `tests/test_invoicing.py` *(edit)*). *[BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line."), [BR-25](../../../../docs/business-requirements.md#invoicing-and-payment "BR-25: Each line invoices exactly once, however many times the invoicing job runs."),
[US-03](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "US-03: Invoice each line when it falls due"), [AC-03.2](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.2: Given an installment due today, when the invoicing job runs, then one customer invoice is posted for it. When the job runs again the same day, no second invoice is created.").*
1. `ir.cron` "Real Estate: nightly run", daily, `user_id` `base.user_root`, code
   `model._cron_nightly()`.
2. `_cron_nightly(today=None)`: step 1 of §5.5 — `_invoice_due_lines(today)` across companies.
   Steps 2–3 come with Story 05; step 4 with Step 7.
3. T6. *Check:* `make test`; run the cron once by hand on `re_dev`.

**Step 6 — Delivery dates and invoices the deposit** (contract *(edit)*,
`tests/test_delivery_closing.py`). *[BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date."), [BR-23](../../../../docs/business-requirements.md#invoicing-and-payment "BR-23: The maintenance deposit is invoiced on its due date. It is money held for the compound's upkeep, not revenue, so it posts to a deposit liability account, never to sales revenue."), [US-11](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "US-11: Record delivery of the unit"), [AC-11.2](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.2: On delivery, a maintenance deposit 'due at delivery' gets the delivery date as its due date and is invoiced."), [AC-11.3](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.3: Installments not yet due stay scheduled as before.").*
1. `action_deliver()`: after the state change, a maintenance line with no date gets the delivery
   date (`sudo()`, the line is locked), then `_invoice_due_lines(today)`.
2. T10. *Check:* `make test`.

**Step 7 — Nightly job: closing paid contracts** (contract *(edit)*,
`tests/test_delivery_closing.py` *(edit)*). *[BR-12](../../../../docs/business-requirements.md#contracts "BR-12: A delivered contract closes automatically, on the next nightly run, when every line on it — down payment, installments, maintenance deposit and any billed late fees — is fully paid, and no accrued late fee is left unbilled. v1 has no late-fee waiver (Chapter 7)."), [US-12](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "US-12: Close the contract when everything is paid"), [AC-12.1](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.1: Given a delivered contract whose last unpaid line has been paid, when the nightly job runs, the contract becomes closed."), [AC-12.2](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.2: A confirmed (not delivered) contract that is fully paid stays confirmed.").*
1. `_cron_close_paid_contracts()`: delivered contracts whose lines are **all** `paid` → `closed`.
   Step 4 of `_cron_nightly()`. (Late fees join the condition in Story 05.)
2. T11, T12. *Check:* `make test`.

**Step 8 — Retention and refundable amount** (contract *(edit)*, form *(edit)*,
`tests/test_cancellation.py`). *[BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step."), [US-09](../../../../docs/business-requirements.md#us-09--cancel-a-contract "US-09: Cancel a contract"), [AC-09.3](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.3: Given the customer paid 858,000 + 4 × 241,313 = 1,823,252, when the manager cancels, retention is 273,488 and refundable is 1,549,764, both recorded on the contract and unchanged after the credit notes are created.").*
1. Contract `retention_amount` and `refundable_amount` (Monetary, read-only, `copy=False`,
   tracked).
2. In `_cancel_with_reason()`, **before** any credit note: paid on down payment + installments
   (line `amount_paid`) → retention = `half_up(paid × retention % ÷ 100)`; refundable = paid −
   retention + paid maintenance deposit. Late fees: none yet (Story 05).
3. T13. *Check:* `make test`.

**Step 9 — Credit notes and cancelled lines** (contract *(edit)*, `tests/test_cancellation.py`
*(edit)*). *[BR-34](../../../../docs/business-requirements.md#cancellation "BR-34: On cancellation, whatever has been invoiced but not paid is credited: a fully unpaid invoice in full, a partly paid one by a credit note for exactly its unpaid remainder, reconciled with it. Lines not yet invoiced are cancelled, and the unit becomes available again. After cancellation every line shows cancelled — set by the module, not read from accounting, where a credited invoice shows as paid."), [AC-09.4](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.4: After cancellation, invoiced-but-unpaid amounts are credited (including the unpaid remainder of a partly paid invoice), future lines are cancelled, every line shows cancelled, and the unit is available.").*
1. After the amounts are stored: for each invoiced line with `amount_residual` > 0, an
   `out_refund` for exactly that amount (same product, account, no tax),
   `reversed_entry_id` = the invoice; post; reconcile its receivable line with the invoice's.
   One path for both cases: an unpaid invoice is credited in full, a partly paid one for its
   remainder. (The standard reversal wizard always credits the full amount.)
2. Then the contract → `cancelled`; every line shows `cancelled` (by the module, not read from
   accounting); the unit is available again (derived, [BR-03](../../../../docs/business-requirements.md#projects-and-units "BR-03: A unit's status — available, reserved, sold, delivered — is derived from its contract and is never typed by hand: no live contract → available; draft contract → reserved; confirmed → sold; delivered or closed → delivered.")).
3. T14. *Check:* `make test`.

**Step 10 — Whole flow + CI stack.** On `re_dev`: create the two liability accounts, set them in
Settings → Real Estate; on the bank journal, set *Outstanding Receipts* on the incoming payment
method. NH/2026/00003 (draft, `NH-STD-8Q`): confirm → down payment invoiced; register a part
payment → partly paid; run the cron; deliver a cash-plan contract, pay, run the cron → closed;
cancel a confirmed contract → retention, credit notes. Log clean. Then `make lint`,
`make test-ci`.

**Step 11 — Docs + PR.** `docs/design-notes/04-accounting-link.md` (the journal entries, why one
invoice per line, `amount_residual` and `in_payment`, the outstanding receipts trap, sudo and the
lock, idempotency, retention before credit notes, the partial credit note, the `l10n_eg` ADR,
negative checks; 3 explain-back questions); `docs/learning-log.md` mistakes rows; `README.md`
*(edit)*: roadmap 03 → done, 04 → in review, a line recommending `l10n_eg`. Done Criteria ticked
in `plan.md` and `plan.ar.md`. PR; CI green; the maintainer merges with "Create a merge commit";
explain-back answers in `docs/learning-log.md`.

## Edge Cases & Failure Modes

1. **No outstanding receipts account** ([BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date.")). The payment then has no journal entry,
   `amount_residual` does not drop and the invoice shows *In payment* with the full amount due.
   Tests use `AccountTestInvoicingCommon`, which sets it; Step 10 sets it on `re_dev`.
2. **`in_payment` is paid.** Community returns `paid`; with the Accountant app the same invoice is
   `in_payment` until bank reconciliation. Both mean paid (T8 patches the hook).
3. **Default sales tax** ([BR-44](../../../../docs/business-requirements.md#invoicing-and-payment "BR-44: Schedule-line invoices carry no taxes in v1, even if the company has default sales taxes. Residential unit sales are VAT-exempt; the treatment of commercial units must be confirmed with a tax advisor.")). `_compute_tax_ids()` fills taxes from the product and the
   account; the line passes `tax_ids` empty and the products have none. T4 sets a company default
   tax and checks `amount_tax` = 0.
4. **Invoiced twice** ([BR-25](../../../../docs/business-requirements.md#invoicing-and-payment "BR-25: Each line invoices exactly once, however many times the invoicing job runs.")). Only lines without `invoice_id` are invoiced. The cron never runs
   twice at once; a confirmation and a job writing the same line in parallel collide on the row
   (Postgres serialization error, the job retries).
5. **Draft contracts are never invoiced** ([BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line.")); a cancelled one neither.
6. **Lead days** ([BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line.")): a line is invoiced N days early, but its due date stays the
   scheduled one (effective due = the later date).
7. **Confirmed late** ([BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).")): a line already due at confirmation is invoiced that day and its
   invoice due date is the confirmation day, so nothing is late for time before confirmation.
8. **No accounting rights.** Managers, agents and the cron are not accountants; invoices and credit
   notes are made with `sudo()` inside the module's own methods, never by opening Odoo's wizards.
   `invoice_id` is shown to accounting users only; everyone else reads the stored state and amounts.
9. **Accounts not set.** Confirmation is refused with the setting's name; the job raises the same
   message (logged) instead of posting to a wrong account.
10. **Deposit due at delivery** has no date and is never picked by the job before delivery
    ([BR-18](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-18: The maintenance deposit = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is not part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date.")); delivery gives it the delivery date (maybe in the past) and invoices it at once.
11. **Retention after credit notes would be wrong** ([BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step.")): a credit note lowers
    `amount_residual` like a payment. So the amounts are computed and stored first, and line
    `amount_paid` leaves credit notes out.
12. **Partial credit** ([BR-34](../../../../docs/business-requirements.md#cancellation "BR-34: On cancellation, whatever has been invoiced but not paid is credited: a fully unpaid invoice in full, a partly paid one by a credit note for exactly its unpaid remainder, reconciled with it. Lines not yet invoiced are cancelled, and the unit becomes available again. After cancellation every line shows cancelled — set by the module, not read from accounting, where a credited invoice shows as paid.")): the reversal wizard credits the full invoice, which would
    "refund" money the customer did pay. A manual credit note for exactly the residual, reconciled.
13. **A fully credited invoice shows *Reversed*, a partly paid one *Paid*** in accounting; both
    lines show `cancelled` because the contract is cancelled.
14. **Closing**: only delivered contracts ([AC-12.2](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.2: A confirmed (not delivered) contract that is fully paid stays confirmed.")); a line not yet invoiced is not paid, so a
    contract with future installments never closes early.
15. **Test base switch.** `BaseCommon` replaces `cls.env` after `super().setUpClass()`; fixtures
    made before it would sit in another company. All fixtures stay after the call.
16. **Log check.** New models / settings without ACL or a view error fail `make test`.

## Test Plan

Tests under `addons/real_estate_eg/tests/`, all `@tagged("post_install", "-at_install")`, on
`RealEstateCommon` (now `AccountTestInvoicingCommon`). "Today" is fixed with `freeze_time`; every
action runs `with_user()` an agent, manager, collections or Invoicing user. Payments go through
`_register_payment()` (Odoo's register-payment wizard).

| # | Test | Proves |
|---|---|---|
| T1 | `test_invoicing.py` — `test_settings_defaults` (retention 15, lead days 0, products have no tax) | [BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step."), [BR-22](../../../../docs/business-requirements.md#invoicing-and-payment "BR-22: Each later line is invoiced automatically on its due date. A company setting allows invoicing N days earlier (default 0). No line is invoiced before its contract is confirmed. One invoice per schedule line — Odoo's multi-due-date payment terms are not used, because late fees, partial payments and BR-25 all work per line.") |
| T2 | `test_invoicing.py` — `test_ac_03_7_advances_account` (down payment invoice: receivable debit 858,000, advances credit 858,000, no income line) | [AC-03.7](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.7: Down payment and installment invoices post to the customer advances account, not to sales revenue.") |
| T3 | `test_invoicing.py` — `test_ac_03_3_maintenance_liability` (Example C deposit at signing → maintenance account) | [AC-03.3](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.3: Given a maintenance deposit falls due, its invoice posts to the maintenance deposit liability account, not to sales revenue.") |
| T4 | `test_invoicing.py` — `test_ac_03_6_no_tax` (company default sales tax set; `amount_tax` 0, no tax lines) | [AC-03.6](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.6: Given the company has a default sales tax, schedule-line invoices still carry no tax.") |
| T5 | `test_invoicing.py` — `test_ac_03_1_invoice_at_confirmation` (Example A at 10 Jan 2027: down payment only; Example C at 31 Jan 2027: down payment + deposit; a contract dated a year back: installments already due too, due date = confirmation day; manager has no accounting rights) | [AC-03.1](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.1: When a contract is confirmed, then every line already due is invoiced immediately — the down payment, and for Example C (Chapter 6) also the maintenance deposit due at signing."), [AC-10.3](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.3: On confirmation the unit shows sold and every line already due is invoiced (BR-21).") |
| T6 | `test_invoicing.py` — `test_ac_03_2_job_invoices_once` (installment due today → one invoice; second run → none; draft contract → none; lead days 5 → invoiced 5 days early with the scheduled due date) | [AC-03.2](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.2: Given an installment due today, when the invoicing job runs, then one customer invoice is posted for it. When the job runs again the same day, no second invoice is created.") |
| T8 | `test_payment_state.py` — `test_ac_03_4_partial_then_paid` (241,313; 141,313 paid → partly paid, 100,000 outstanding; rest → paid; `in_payment` patched → paid) | [AC-03.4](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.4: Given a 241,313 invoice and a bank journal with an outstanding receipts account, when a payment of 141,313 is registered, the line shows partly paid with 100,000 outstanding; when the rest is paid, it shows paid (also while accounting shows the invoice In payment).") |
| T9 | `test_payment_state.py` — `test_ac_03_5_contract_totals` (paid and outstanding after payments; agent and collections read them without `AccessError`) | [AC-03.5](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.5: The contract shows total paid and total outstanding, both computed from accounting.") |
| T10 | `test_delivery_closing.py` — `test_ac_11_2_deposit_due_on_delivery` (deposit dated and invoiced to the maintenance account; next installment still scheduled) | [AC-11.2](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.2: On delivery, a maintenance deposit 'due at delivery' gets the delivery date as its due date and is invoiced."), [AC-11.3](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.3: Installments not yet due stay scheduled as before.") |
| T11 | `test_delivery_closing.py` — `test_ac_12_1_close_when_paid` (cash plan, delivered; one line unpaid → job keeps it delivered; paid → closed) | [AC-12.1](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.1: Given a delivered contract whose last unpaid line has been paid, when the nightly job runs, the contract becomes closed.") |
| T12 | `test_delivery_closing.py` — `test_ac_12_2_confirmed_paid_stays_open` | [AC-12.2](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.2: A confirmed (not delivered) contract that is fully paid stays confirmed.") |
| T13 | `test_cancellation.py` — `test_ac_09_3_retention_example_e` (Example E: 1,823,252 paid → 273,488 / 1,549,764; unchanged after the credit notes) | [AC-09.3](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.3: Given the customer paid 858,000 + 4 × 241,313 = 1,823,252, when the manager cancels, retention is 273,488 and refundable is 1,549,764, both recorded on the contract and unchanged after the credit notes are created.") |
| T14 | `test_cancellation.py` — `test_ac_09_4_credit_notes` (unpaid invoice credited in full; partly paid credited for the remainder and reconciled, residual 0; future lines cancelled; every line `cancelled`; unit available) | [AC-09.4](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.4: After cancellation, invoiced-but-unpaid amounts are credited (including the unpaid remainder of a partly paid invoice), future lines are cancelled, every line shows cancelled, and the unit is available.") |
| T15 | `make test`, `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

(T7 is folded into T5: the effective due date of a line invoiced late.)

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: drop the empty `tax_ids` on the invoice line → T4 fails.
- N2: drop the "no `invoice_id` yet" filter → T6 fails (second invoice).
- N3: count only `paid`, not `in_payment` → T8 fails.
- N4: compute the retention after the credit notes → T13 fails.
- N5: close confirmed contracts too → T12 fails.
- N6: remove Outstanding Receipts from the bank method line → T8 fails (amount due does not drop).

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/04-accounting-link
make test        # T1–T6, T8–T14 pass with the 37 earlier tests, log clean
make lint        # pre-commit green
make test-ci     # same tests in the CI Docker stack
make run ARGS="-u real_estate_eg"   # Step 10 walk-through on re_dev; log clean
gh pr checks     # pre-commit + test green on the PR
gh run list --branch main --limit 1   # green after merge
```

## Done Criteria

- [x] **[AC-03.1](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.1: When a contract is confirmed, then every line already due is invoiced immediately — the down payment, and for Example C (Chapter 6) also the maintenance deposit due at signing.")** On confirmation every line already due is invoiced at once: the down payment,
  and for Example C also the maintenance deposit due at signing. *Proof:* T5.
- [x] **[AC-03.2](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.2: Given an installment due today, when the invoicing job runs, then one customer invoice is posted for it. When the job runs again the same day, no second invoice is created.")** The nightly job posts one invoice for an installment due today; a second run
  the same day creates none. *Proof:* T6.
- [x] **[AC-03.3](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.3: Given a maintenance deposit falls due, its invoice posts to the maintenance deposit liability account, not to sales revenue.")** A maintenance deposit invoice posts to the maintenance deposit liability
  account, not to revenue. *Proof:* T3, T10.
- [x] **[AC-03.4](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.4: Given a 241,313 invoice and a bank journal with an outstanding receipts account, when a payment of 141,313 is registered, the line shows partly paid with 100,000 outstanding; when the rest is paid, it shows paid (also while accounting shows the invoice In payment).")** 241,313 invoice, 141,313 paid through a bank journal with Outstanding
  Receipts → line partly paid, 100,000 outstanding; rest paid → paid, also when accounting shows
  *In payment*. *Proof:* T8.
- [x] **[AC-03.5](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.5: The contract shows total paid and total outstanding, both computed from accounting.")** The contract shows total paid and total outstanding (invoiced but unpaid),
  both computed from accounting. *Proof:* T9.
- [x] **[AC-03.6](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.6: Given the company has a default sales tax, schedule-line invoices still carry no tax.")** With a company default sales tax, schedule-line invoices still carry no tax.
  *Proof:* T4.
- [x] **[AC-03.7](../../../../docs/business-requirements.md#us-03--invoice-each-line-when-it-falls-due "AC-03.7: Down payment and installment invoices post to the customer advances account, not to sales revenue.")** Down payment and installment invoices post to the customer advances account,
  not to revenue. *Proof:* T2.
- [x] **[AC-12.1](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.1: Given a delivered contract whose last unpaid line has been paid, when the nightly job runs, the contract becomes closed.")** A delivered contract whose last unpaid line is paid closes on the next nightly
  run. *Proof:* T11.
- [x] **[AC-12.2](../../../../docs/business-requirements.md#us-12--close-the-contract-when-everything-is-paid "AC-12.2: A confirmed (not delivered) contract that is fully paid stays confirmed.")** A confirmed (not delivered) contract that is fully paid stays confirmed.
  *Proof:* T12.
- [x] **[AC-09.3](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.3: Given the customer paid 858,000 + 4 × 241,313 = 1,823,252, when the manager cancels, retention is 273,488 and refundable is 1,549,764, both recorded on the contract and unchanged after the credit notes are created.")** Example E: 1,823,252 paid → retention 273,488, refundable 1,549,764, stored on
  the contract and unchanged after the credit notes. *Proof:* T13.
- [x] **[AC-09.4](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.4: After cancellation, invoiced-but-unpaid amounts are credited (including the unpaid remainder of a partly paid invoice), future lines are cancelled, every line shows cancelled, and the unit is available.")** After cancellation invoiced-but-unpaid amounts are credited (a partly paid
  invoice for its remainder), future lines are cancelled, every line shows cancelled, the unit is
  available. *Proof:* T14.
- [x] **[AC-10.3](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.3: On confirmation the unit shows sold and every line already due is invoiced (BR-21).")** *(invoicing part)* On confirmation every line already due is invoiced
  ([BR-21](../../../../docs/business-requirements.md#invoicing-and-payment "BR-21: On confirmation, every line due on or before the confirmation date is invoiced at once — the down payment, a maintenance deposit due at signing, and any installment already due.")). *Proof:* T5.
- [x] **[AC-11.2](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.2: On delivery, a maintenance deposit 'due at delivery' gets the delivery date as its due date and is invoiced.")** On delivery a deposit "due at delivery" gets the delivery date and is
  invoiced. *Proof:* T10.
- [x] **[AC-11.3](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.3: Installments not yet due stay scheduled as before.")** Installments not yet due stay scheduled after delivery. *Proof:* T10.
