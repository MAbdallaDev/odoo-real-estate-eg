# 05 — Overdue lines, late fees and the at-risk flag

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/05-late-fees/intake.md`
- **Branch:** `story/05-late-fees`
- **Status:** Done Criteria approved 2026-11-25 (grace and at-risk days are settings; unpaid late-fee
  invoices are credited on cancellation); all steps done; Done Criteria met (72 tests green,
  test-ci green); in review

---

## Prerequisites

- Story 04 merged (PR #4, merge commit `8dd75e0`); CI green on `main`; 52 tests pass locally.
- Local `main` clean and in sync with `origin/main`.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Nothing new to install. "Today" in tests: `odoo/tests/common.py` imports `freezegun` and replaces
  `freezegun.freeze_time` with its own `freeze_time` class (works as a decorator, a class decorator
  or a `with` block), so `from freezegun import freeze_time` — already used by Story 04's tests —
  gets Odoo's version.
- **Parallel work:** Story 08 runs in its own worktree on `re_test_08` / `re_dev_08`, ports
  8039/8049. This story uses `re_test` / `re_dev` and free ports
  (`make test ARGS="--http-port 8097 --gevent-port 8098"`). The PR that merges second rebases on
  `main` and fixes small conflicts (`__manifest__.py`, README, learning log).
- **For Step 10 on `re_dev`:** an *Other Income* account for late fees, set in Settings → Real
  Estate. Step 10 says how.

## Story Goal

Every night the job computes, for each invoiced line of a live contract, its **days past due**, its
**overdue** flag and its **accrued late fee** — from the effective due date, the line's payment
history in accounting and the as-of date, never by adding to last night's number. A contract with a
line more than 60 days past due is flagged **at risk**; nothing is ever cancelled automatically. A
collections officer or sales manager bills a contract's unbilled fees as **one invoice**, rounded
once to whole EGP. A delivered contract closes only when its late fees are billed and paid too.

The fee for one line, as a formula (rate r = 1 % per month, a company setting):

> fee = min( Σ over days d with effective due ≤ d < end : unpaid(d) × r ÷ 30 , cap % × amount )
>
> end = the day the line was fully paid, or the as-of date if it is still unpaid; unpaid(d) = amount −
> payments dated on or before d; the fee is 0 if the line was never overdue.

Not in this story: late-fee waivers, bounced-cheque fees (Chapter 7); notifications; the due /
overdue screens and aging buckets (Story 07); record rules (Story 06); demo data (Story 10).

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/05-late-fees/intake.md` — the ACs below, §5.5 nightly job, §6.4
  policy, Example D.
- `docs/business-requirements.md` — [BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date."), [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).")–[BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own."), [BR-12](../../../../docs/business-requirements.md#contracts "BR-12: A delivered contract closes automatically, on the next nightly run, when every line on it — down payment, installments, maintenance deposit and any billed late fees — is fully paid, and no accrued late fee is left unbilled. v1 has no late-fee waiver (Chapter 7).") (closing waits for
  late fees), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.") (who bills), [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).") (half up, exact decimals); §5.5; Example D in §6.6.
- `docs/design-notes/04-accounting-link.md` — one invoice per line, `amount_residual`, the
  outstanding receipts trap, sudo and the [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.") lock.
- `addons/real_estate_eg/models/real_estate_installment.py` — `invoice_id`, `invoice_date`,
  `date_effective_due` (already the later of due date and invoice date), `state`,
  `_compute_payment()`, `_line_product_and_account()`, `_create_invoices()`.
- `addons/real_estate_eg/models/real_estate_contract.py` — `_cron_nightly(today=None)` (steps 2–3
  left to this story), `_cron_close_paid_contracts()`, `_check_manager()`,
  `_cancellation_amounts()`.
- `addons/real_estate_eg/models/res_company.py`, `res_config_settings.py`,
  `views/res_config_settings_views.xml`, `data/product_data.xml` — where the new settings and the
  late-fee product go.
- `addons/real_estate_eg/tools/schedule.py` — `half_up()` (whole EGP, half up, `Decimal`); the
  late-fee math follows the same "pure function, tests first" shape.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon` (on `AccountTestInvoicingCommon`),
  `_example_a()`, `_line()`.
- `addons/real_estate_eg/tests/test_payment_state.py` — `_installment_1_invoiced()`, the Example D
  starting point.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/addons/account/models/account_move.py` —
  `_get_all_reconciled_invoice_partials()`: every partial reconciliation on the invoice's
  receivable line, with the amount and the counterpart line (`aml`, whose `date` is the payment's
  accounting date), sorted by date. This is the payment history ([BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date."): a payment counts from
  its own date). Counterparts whose move is a credit note (`out_refund`) are not payments.
- `odoo-src/odoo/addons/account/wizard/account_payment_register.py` — `payment_date`: a payment
  registered today can carry an earlier date ([AC-05.4](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.4: Running the nightly job twice on the same day gives the same totals as running it once. Skipping a night and running the next day gives the same totals as running both nights. A payment entered late with an earlier date gives the fee it would have had if entered on time."), the late-entered payment).
- `odoo-src/odoo/addons/account/tests/common.py` — `_register_payment(record, **kwargs)` passes
  `kwargs` (e.g. `amount`, `payment_date`) to the wizard.
- `odoo-src/odoo/odoo/orm/fields_numeric.py` — `Monetary.convert_to_cache()` rounds to the currency
  (`currency.round()`), so a `Monetary` field can **not** hold the unrounded fee; `Float` without
  `digits` keeps it as is.
- `odoo-src/odoo/odoo/addons/base/models/res_currency.py` — `round()` uses `float_round()`, half
  up: a `Monetary` display field shows 3,619.695 as 3,619.70.
- `odoo-src/odoo/addons/account/models/account_account.py` — account types `income`,
  `income_other` (the late-fee account's domain).
- `odoo-src/odoo/odoo/tests/common.py` — `freeze_time` (see Prerequisites), `BaseCase`.

## Implementation tasks

Small steps, in order. The user asked for speed: all steps run one after another without stopping,
**one commit per step**, each ending with Key points (built + ids, Odoo concept, trap, one-line takeaway;
the journal entry when the step creates one).

Files are new unless marked *(edit)*. All under `addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Branch and plan commit.** `git switch -c story/05-late-fees` from up-to-date `main`;
commit this plan and the overview row.

**Step 1 — Late-fee settings and product** (`models/res_company.py` *(edit)*,
`models/res_config_settings.py` *(edit)*, `views/res_config_settings_views.xml` *(edit)*,
`data/product_data.xml` *(edit)*, `tests/test_late_fees.py`, `tests/__init__.py` *(edit)*).
*[BR-27](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-27: Once a line is overdue, a late fee accrues for every day d from its effective due date up to, but not including, the day it is fully paid — not from the end of the grace period — on the amount unpaid on day d (a payment counts from its own date), at 1% per month (1/30 of 1% per day; a company setting). Simple interest, never compounding. Every schedule line accrues — down payment, installments and maintenance deposit; late-fee invoices never do. Daily amounts are not rounded day by day: the total is computed from the unrounded daily amounts and rounded once (to piastres for display, to whole EGP when billed). Rounding each day would drift — 45 days on 241,313 gives 3,619.695 (shown 3,619.70) but 3,619.80 if each day were rounded to 80.44."), [BR-28](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-28: Total late fees on one line are capped at 10% of that line's amount."), [BR-30](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-30: Late fees are billed deliberately: a collections officer or sales manager bills a contract's unbilled fees in one invoice. Each line's unbilled fee = accrued − already billed, both kept unrounded; the invoice total is rounded once to whole EGP. The system never bills them on its own.").*
1. `res.company`: `re_late_fee_rate` (Float, % per month, default 1), `re_late_fee_cap` (Float, %
   of the line, default 10), `re_late_fee_account_id` (Many2one `account.account`, types `income`
   / `income_other`), `re_grace_days` (Integer, default 7, [BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).")), `re_at_risk_days` (Integer,
   default 60, [BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own.")) — every §6.4 policy value in one place. Constraints: rate and cap between
   0 and 100, days not negative. Same five in `res.config.settings` (`related`, `readonly=False`)
   and in the Real Estate settings block.
2. `data/product_data.xml`: a fourth service product, Late Fee, no customer taxes.
3. `RealEstateCommon`: creates an *Other Income* account and sets it on the company.
4. T1. *Check:* `make test`.

**Step 2 — The late-fee arithmetic, tests first** (`tools/late_fee.py`,
`tests/test_late_fee_math.py`). *[BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days)."), [BR-27](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-27: Once a line is overdue, a late fee accrues for every day d from its effective due date up to, but not including, the day it is fully paid — not from the end of the grace period — on the amount unpaid on day d (a payment counts from its own date), at 1% per month (1/30 of 1% per day; a company setting). Simple interest, never compounding. Every schedule line accrues — down payment, installments and maintenance deposit; late-fee invoices never do. Daily amounts are not rounded day by day: the total is computed from the unrounded daily amounts and rounded once (to piastres for display, to whole EGP when billed). Rounding each day would drift — 45 days on 241,313 gives 3,619.695 (shown 3,619.70) but 3,619.80 if each day were rounded to 80.44."), [BR-28](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-28: Total late fees on one line are capped at 10% of that line's amount."), [BR-29](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-29: A line's accrued late fee is computed, not added up night by night: from its effective due date, its payment history in accounting and the as-of date, then capped (BR-28). The nightly job stores the result. Running it twice, skipping a night, or entering a payment late with an earlier date all give the same answer as one correct computation."), [BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695)."),
[AC-05.2](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.2: Given the same line is paid in full on 25 May 2027 (45 days after due date), its total accrued late fee is 3,619.695, shown as 3,619.70 → billed as 3,620 EGP."), [AC-05.3](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.3: Given 141,313 is paid on 30 Apr and 100,000 on 25 May, the accrued fee is 20 days on 241,313 plus 25 days on 100,000 = 2,442.09 → billed as 2,442."), [AC-05.5](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.5: A line's accrued fee never exceeds 10% of its amount."), [AC-05.8](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.8: The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one."), [AC-05.10](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.10: Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.").*
1. Pure functions, no ORM, `Decimal` only. `days_past_due(effective_due, as_of)`;
   `paid_date(amount, payments)` — the date cumulative payments reach the amount, or `None`;
   `compute_late_fee(amount, effective_due, payments, as_of, monthly_rate, cap_percent,
   grace_days)` → unrounded `Decimal`. `payments` is a list of `(date, amount)`; the policy values
   come from the company settings.
2. Day rule: a day d is charged when `effective_due ≤ d < end`, end = paid date if ≤ as-of, else
   as-of. Charged only if the line was **overdue** on some day x ≤ as-of while unpaid
   (x − effective due > grace days). Daily amount = unpaid(d) × rate ÷ 100 ÷ 30, never rounded; total capped
   at cap % × amount.
3. T2 (`BaseCase`, like `test_schedule_math.py`). *Check:* `make test`.

**Step 3 — Payment history from accounting** (`models/real_estate_installment.py` *(edit)*,
`tests/test_late_fees.py` *(edit)*). *[BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date."), [BR-29](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-29: A line's accrued late fee is computed, not added up night by night: from its effective due date, its payment history in accounting and the as-of date, then capped (BR-28). The nightly job stores the result. Running it twice, skipping a night, or entering a payment late with an earlier date all give the same answer as one correct computation.").*
1. `_payment_history()`: `(date, amount)` pairs from
   `invoice_id._get_all_reconciled_invoice_partials()`, as superuser; leaves out credit notes and
   exchange-difference lines; date = the counterpart line's `date`.
2. T3. *Check:* `make test`.

**Step 4 — Overdue and accrued fee on the line** (installment *(edit)*, `tests/test_late_fees.py`
*(edit)*). *[BR-26](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-26: A line's effective due date is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. Days past due = today − effective due date. A line is overdue when it is not fully paid and today is after effective due date + grace period (7 days).")–[BR-29](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-29: A line's accrued late fee is computed, not added up night by night: from its effective due date, its payment history in accounting and the as-of date, then capped (BR-28). The nightly job stores the result. Running it twice, skipping a night, or entering a payment late with an earlier date all give the same answer as one correct computation."), [US-05](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "US-05: Flag overdue lines and accrue late fees every night"), [AC-05.1](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.1: Given an installment of 241,313 due 10 Apr 2027 and unpaid, on 15 Apr and on 17 Apr (due date + 7) it is not overdue; on 18 Apr it is overdue."), [AC-05.2](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.2: Given the same line is paid in full on 25 May 2027 (45 days after due date), its total accrued late fee is 3,619.695, shown as 3,619.70 → billed as 3,620 EGP."), [AC-05.3](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.3: Given 141,313 is paid on 30 Apr and 100,000 on 25 May, the accrued fee is 20 days on 241,313 plus 25 days on 100,000 = 2,442.09 → billed as 2,442."), [AC-05.5](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.5: A line's accrued fee never exceeds 10% of its amount."),
[AC-05.8](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.8: The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one."), [AC-05.10](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.10: Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.").*
1. Line fields: `days_past_due` (Integer, stored, written by the job), `is_overdue` (stored
   compute: not paid and `days_past_due` > the company's grace days — a payment clears it at once), `late_fee_accrued`
   and `late_fee_billed` (**`Float`, unrounded**), `late_fee_unbilled` (stored compute: accrued −
   billed), `late_fee_display` (`Monetary`, not stored: accrued rounded to piastres for the screen),
   `late_fee_final` (Boolean: computed after the line was fully paid).
2. `_recompute_late_fees(as_of)`: for each line, reads the history, writes the five values as
   superuser (the line is locked, [BR-19](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-19: The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked.")). Not invoiced → nothing to compute.
3. T4, T5, T6, T7. *Check:* `make test`.

**Step 5 — Nightly job steps 2 and 3, and the at-risk flag** (contract *(edit)*,
`tests/test_late_fees.py` *(edit)*). *[BR-29](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-29: A line's accrued late fee is computed, not added up night by night: from its effective due date, its payment history in accounting and the as-of date, then capped (BR-28). The nightly job stores the result. Running it twice, skipping a night, or entering a payment late with an earlier date all give the same answer as one correct computation."), [BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own."), [AC-05.4](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.4: Running the nightly job twice on the same day gives the same totals as running it once. Skipping a night and running the next day gives the same totals as running both nights. A payment entered late with an earlier date gives the fee it would have had if entered on time."), [AC-05.6](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.6: Given a line becomes 61 days past due, its contract is flagged at risk; the contract is not cancelled.").*
1. `_cron_late_fees(today)`: invoiced lines of confirmed or delivered contracts that are not paid
   **or** not `late_fee_final` (§5.5: overdue lines and lines paid since the last run) →
   `_recompute_late_fees(today)`.
2. Contract `at_risk` (Boolean, stored compute, tracked): any line not paid with `days_past_due` >
   the company's at-risk days (60). Cleared by itself when no such line remains; nothing cancels the contract.
3. `_cron_nightly()` runs: invoice (1), late fees (2), at risk follows (3), close (4).
4. T8, T9. *Check:* `make test`.

**Step 6 — Bill late fees** (contract *(edit)*, `tests/test_late_fees.py` *(edit)*). *[BR-30](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-30: Late fees are billed deliberately: a collections officer or sales manager bills a contract's unbilled fees in one invoice. Each line's unbilled fee = accrued − already billed, both kept unrounded; the invoice total is rounded once to whole EGP. The system never bills them on its own."),
[BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."), [AC-05.7](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.7: When a collections officer or sales manager bills late fees on a contract, one invoice is created for all unbilled fees, its total rounded once; billing again immediately creates nothing."), [AC-05.9](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.9: A late-fee invoice that is itself paid late accrues no late fee.").*
1. Contract `late_fee_invoice_ids` (Many2many `account.move`, read-only, `copy=False`, accounting
   users only), `late_fee_accrued` and `late_fee_unbilled` (`Monetary`, sums of the lines, rounded
   once).
2. `action_bill_late_fees()`: collections officer or sales manager only (`AccessError` otherwise);
   confirmed or delivered contracts. Total = `half_up(Σ unbilled)`; 0 → nothing. Else one
   `out_invoice` as superuser: Late Fee product, the late-fee account, no tax, price = total;
   post; link it; each line's `late_fee_billed` += its unbilled (unrounded); a chatter note with the
   amount for users without invoice rights.
3. Late-fee invoices are not schedule lines, so the job never reads them: they never accrue.
4. T10, T11. *Check:* `make test`.

**Step 7 — Closing waits for late fees** (contract *(edit)*, `tests/test_delivery_closing.py`
*(edit)*). *[BR-12](../../../../docs/business-requirements.md#contracts "BR-12: A delivered contract closes automatically, on the next nightly run, when every line on it — down payment, installments, maintenance deposit and any billed late fees — is fully paid, and no accrued late fee is left unbilled. v1 has no late-fee waiver (Chapter 7).").*
1. `_cron_close_paid_contracts()`: also every late-fee invoice paid (or in payment) and
   `half_up(Σ unbilled) == 0`.
2. T12. *Check:* `make test`.

**Step 8 — Cancellation credits unpaid late-fee invoices** (installment / contract *(edit)*,
`tests/test_cancellation.py` *(edit)*). *[BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step."), [BR-34](../../../../docs/business-requirements.md#cancellation "BR-34: On cancellation, whatever has been invoiced but not paid is credited: a fully unpaid invoice in full, a partly paid one by a credit note for exactly its unpaid remainder, reconciled with it. Lines not yet invoiced are cancelled, and the unit becomes available again. After cancellation every line shows cancelled — set by the module, not read from accounting, where a credited invoice shows as paid.").*
1. The credit-note code of `_credit_unpaid()` is split so it can credit any invoice for its
   residual with a given product and account; `_cancel_with_reason()` also credits each unpaid
   late-fee invoice (Late Fee product, late-fee account), after the retention is stored.
2. Retention and refundable amount stay as in Story 04: late fees are neither in "paid" nor
   refunded.
3. T13. *Check:* `make test`.

**Step 9 — Screens** (`views/real_estate_contract_views.xml` *(edit)*). *[US-05](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "US-05: Flag overdue lines and accrue late fees every night"), [BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own.").*
1. Schedule list: days past due, overdue (red row), accrued fee (piastres), billed.
2. Contract form: "Bill Late Fees" button (collections, managers; confirmed / delivered), an
   "At risk" ribbon, accrued and unbilled in the totals footer, late-fee invoices for accounting
   users. List: at-risk badge; search filters "At risk" and "Overdue".
3. *Check:* `make test` (log clean); `-u` on `re_dev`.

**Step 10 — Whole flow + CI stack.** On `re_dev`: create an *Other Income* account "Late Fees",
set it in Settings → Real Estate. A confirmed contract with an invoiced line: run
`_cron_nightly()` from `make shell` for dates past grace and past 60 days (inside a rolled-back
transaction), bill late fees as a collections user, see the invoice. Log clean. Then `make lint`,
`make test-ci`.

**Step 11 — Docs + PR.** `docs/design-notes/05-late-fees.md` (computed not accumulated, the day
rule, unrounded `Float` vs `Monetary`, payment history from partials, `late_fee_final`, billing as
superuser, the journal entry, negative checks; 3 explain-back questions); `docs/learning-log.md`;
`README.md` *(edit)*: roadmap 04 → done, 05 → in review, the late-fee account in setup. Done
Criteria ticked in `plan.md` and `plan.ar.md`. PR; CI green; the maintainer merges with "Create a
merge commit"; explain-back answers in `docs/learning-log.md` (Story 04's too, reviewed).

## Edge Cases & Failure Modes

1. **Grace forgives only if you pay within it** ([BR-27](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-27: Once a line is overdue, a late fee accrues for every day d from its effective due date up to, but not including, the day it is fully paid — not from the end of the grace period — on the amount unpaid on day d (a payment counts from its own date), at 1% per month (1/30 of 1% per day; a company setting). Simple interest, never compounding. Every schedule line accrues — down payment, installments and maintenance deposit; late-fee invoices never do. Daily amounts are not rounded day by day: the total is computed from the unrounded daily amounts and rounded once (to piastres for display, to whole EGP when billed). Rounding each day would drift — 45 days on 241,313 gives 3,619.695 (shown 3,619.70) but 3,619.80 if each day were rounded to 80.44.")). Paid on day 8 after the effective due
   date → never overdue → fee 0. Paid on day 9 → it was overdue on day 8 → 9 days charged, from the
   effective due date, not from the end of grace.
2. **Confirmed late** ([AC-05.10](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.10: Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.")): effective due date = invoice date, so 10–29 Jan cost nothing.
3. **Rounding drift** ([AC-05.8](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.8: The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one.")): 45 × 80.44 = 3,619.80. The sum is kept unrounded and stored in a
   `Float`; a `Monetary` field would round on write.
4. **Float noise** ([BR-45](../../../../docs/business-requirements.md#payment-plans-and-the-schedule "BR-45: All money arithmetic rounds half up with exact decimal arithmetic (Decimal, or Odoo's float_round, which corrects binary-float error) — never plain float. Several test values sit exactly on a rounding tie (e.g. 3,619.695).")): the math runs on `Decimal(str(x))`; the 3,619.695 tie is rounded by
   `float_round` / `half_up`, never `round()`.
5. **Run twice, skip a night** ([AC-05.4](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.4: Running the nightly job twice on the same day gives the same totals as running it once. Skipping a night and running the next day gives the same totals as running both nights. A payment entered late with an earlier date gives the fee it would have had if entered on time.")): the fee is a function of (history, as-of), so the
   stored value is overwritten, never added to.
6. **Payment entered late with an earlier date**: the history uses the payment's own date, and the
   line was not `late_fee_final` yet, so the next run recomputes it.
7. **A paid line is final once computed**; if the payment is later unreconciled the line is no longer
   paid and is picked up again.
8. **Cap** ([BR-28](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-28: Total late fees on one line are capped at 10% of that line's amount.")): 10 % of 241,313 = 24,131.30, reached after 300 days unpaid.
9. **Late-fee invoices never accrue** ([AC-05.9](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.9: A late-fee invoice that is itself paid late accrues no late fee.")) and never make a contract at risk: they are not
   schedule lines.
10. **Billing twice** ([AC-05.7](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.7: When a collections officer or sales manager bills late fees on a contract, one invoice is created for all unbilled fees, its total rounded once; billing again immediately creates nothing.")): billed = accrued after the first invoice, so the second total is
    0 and nothing is created. A total under 0.50 EGP rounds to 0 and is not billed.
11. **Rights** ([BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.")): agents and accountants cannot bill; collections officers have no invoice
    rights, so the invoice is created as superuser inside the action.
12. **At risk** ([BR-31](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-31: A contract with any line more than 60 days past due is flagged at risk of cancellation. The system never cancels a contract on its own.")): 60 days past due is not at risk, 61 is. Paying the line clears it at
    once (stored compute on the line state), without waiting for the job.
13. **Cancelled contracts** are not computed any more; their at-risk flag is cleared. Unpaid
    late-fee invoices are credited for their remainder, like schedule lines ([BR-34](../../../../docs/business-requirements.md#cancellation "BR-34: On cancellation, whatever has been invoiced but not paid is credited: a fully unpaid invoice in full, a partly paid one by a credit note for exactly its unpaid remainder, reconciled with it. Lines not yet invoiced are cancelled, and the unit becomes available again. After cancellation every line shows cancelled — set by the module, not read from accounting, where a credited invoice shows as paid.")); paid ones
    are not refunded ([BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step.")); fees never billed are dropped.
14. **Closing** ([BR-12](../../../../docs/business-requirements.md#contracts "BR-12: A delivered contract closes automatically, on the next nightly run, when every line on it — down payment, installments, maintenance deposit and any billed late fees — is fully paid, and no accrued late fee is left unbilled. v1 has no late-fee waiver (Chapter 7).")): a fully paid delivered contract with fees unbilled or unpaid stays
    delivered.
15. **Timezone**: the job uses `fields.Date.context_today()` of the superuser; tests pass the date.

## Test Plan

Tests under `addons/real_estate_eg/tests/`, `@tagged("post_install", "-at_install")`. ORM tests on
`RealEstateCommon`; payments through `_register_payment(invoice, amount=…, payment_date=…)`; the job
is called with an explicit date under `freeze_time`; billing runs `with_user()` collections, manager,
agent and accountant.

| # | Test | Proves |
|---|---|---|
| T1 | `test_late_fees.py` — `test_settings_defaults` (rate 1, cap 10, Late Fee product has no tax) | [BR-27](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-27: Once a line is overdue, a late fee accrues for every day d from its effective due date up to, but not including, the day it is fully paid — not from the end of the grace period — on the amount unpaid on day d (a payment counts from its own date), at 1% per month (1/30 of 1% per day; a company setting). Simple interest, never compounding. Every schedule line accrues — down payment, installments and maintenance deposit; late-fee invoices never do. Daily amounts are not rounded day by day: the total is computed from the unrounded daily amounts and rounded once (to piastres for display, to whole EGP when billed). Rounding each day would drift — 45 days on 241,313 gives 3,619.695 (shown 3,619.70) but 3,619.80 if each day were rounded to 80.44."), [BR-28](../../../../docs/business-requirements.md#overdue-lines-and-late-fees "BR-28: Total late fees on one line are capped at 10% of that line's amount.") |
| T2 | `test_late_fee_math.py` — Example D full (3,619.695; 3,619.70; 3,620; not 3,619.80), Example D in two parts (2,442.0867 → 2,442.09 → 2,442), paid within grace → 0, paid day 9 → 9 days, cap, confirmed late (effective due 30 Jan, no fee for 10–29 Jan), days past due | [AC-05.2](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.2: Given the same line is paid in full on 25 May 2027 (45 days after due date), its total accrued late fee is 3,619.695, shown as 3,619.70 → billed as 3,620 EGP."), [AC-05.3](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.3: Given 141,313 is paid on 30 Apr and 100,000 on 25 May, the accrued fee is 20 days on 241,313 plus 25 days on 100,000 = 2,442.09 → billed as 2,442."), [AC-05.5](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.5: A line's accrued fee never exceeds 10% of its amount."), [AC-05.8](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.8: The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one."), [AC-05.10](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.10: Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.") |
| T3 | `test_late_fees.py` — `test_payment_history` (two payments with their own dates; a payment entered on 25 May dated 30 Apr counts from 30 Apr) | [BR-24](../../../../docs/business-requirements.md#invoicing-and-payment "BR-24: Whether a line is paid, partly paid or unpaid is read from its invoice in accounting; nobody types 'paid'. Amounts come from the invoice's amount due (amount_residual); an invoice shown as In payment counts as paid. Bank and cash journals use an outstanding receipts account, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date.") |
| T4 | `test_late_fees.py` — `test_ac_05_1_overdue_after_grace` (not overdue 15 and 17 Apr; overdue 18 Apr; a payment clears it) | [AC-05.1](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.1: Given an installment of 241,313 due 10 Apr 2027 and unpaid, on 15 Apr and on 17 Apr (due date + 7) it is not overdue; on 18 Apr it is overdue.") |
| T5 | `test_late_fees.py` — `test_ac_05_2_example_d_full` and `test_ac_05_3_example_d_parts` (job on 25 May; stored unrounded; display 3,619.70 / 2,442.09) | [AC-05.2](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.2: Given the same line is paid in full on 25 May 2027 (45 days after due date), its total accrued late fee is 3,619.695, shown as 3,619.70 → billed as 3,620 EGP."), [AC-05.3](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.3: Given 141,313 is paid on 30 Apr and 100,000 on 25 May, the accrued fee is 20 days on 241,313 plus 25 days on 100,000 = 2,442.09 → billed as 2,442."), [AC-05.8](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.8: The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one.") |
| T6 | `test_late_fees.py` — `test_ac_05_5_cap` (unpaid 400 days → 24,131.30) | [AC-05.5](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.5: A line's accrued fee never exceeds 10% of its amount.") |
| T7 | `test_late_fees.py` — `test_ac_05_10_confirmed_late` (dated 10 Jan, confirmed 30 Jan; not overdue 6 Feb; fee counts from 30 Jan) | [AC-05.10](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.10: Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.") |
| T8 | `test_late_fees.py` — `test_ac_05_4_idempotent` (twice the same day = once; skip a night = both nights; late-entered earlier payment = on-time fee) | [AC-05.4](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.4: Running the nightly job twice on the same day gives the same totals as running it once. Skipping a night and running the next day gives the same totals as running both nights. A payment entered late with an earlier date gives the fee it would have had if entered on time.") |
| T9 | `test_late_fees.py` — `test_ac_05_6_at_risk` (60 days → no; 61 → yes, still confirmed; paid → cleared) | [AC-05.6](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.6: Given a line becomes 61 days past due, its contract is flagged at risk; the contract is not cancelled.") |
| T10 | `test_late_fees.py` — `test_ac_05_7_bill_once` (collections bills: one invoice 3,620, Late Fee account, no tax; again → nothing; manager can, agent and accountant get `AccessError`) | [AC-05.7](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.7: When a collections officer or sales manager bills late fees on a contract, one invoice is created for all unbilled fees, its total rounded once; billing again immediately creates nothing.") |
| T11 | `test_late_fees.py` — `test_ac_05_9_fee_invoice_never_accrues` (late-fee invoice unpaid 90 days; job runs; accrued unchanged, not at risk) | [AC-05.9](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.9: A late-fee invoice that is itself paid late accrues no late fee.") |
| T12 | `test_delivery_closing.py` — `test_br_12_close_waits_for_late_fees` (fully paid delivered contract with an unbilled fee stays delivered; billed and unpaid stays; paid → closed) | [BR-12](../../../../docs/business-requirements.md#contracts "BR-12: A delivered contract closes automatically, on the next nightly run, when every line on it — down payment, installments, maintenance deposit and any billed late fees — is fully paid, and no accrued late fee is left unbilled. v1 has no late-fee waiver (Chapter 7).") |
| T13 | `test_cancellation.py` — `test_br_34_credit_late_fee_invoice` (an unpaid late-fee invoice is credited in full and reconciled; a paid one is untouched; retention unchanged) | [BR-33](../../../../docs/business-requirements.md#cancellation "BR-33: On cancelling a confirmed contract, the system computes the retention — 15% (a company setting) of what the customer has paid against the down payment and installments, rounded to whole EGP — from actual payments, before any credit note is created. Refundable amount = that paid amount − retention, plus any paid maintenance deposit in full; paid late fees are not refunded. Both are recorded on the contract. Issuing the refund is the accountant's manual step."), [BR-34](../../../../docs/business-requirements.md#cancellation "BR-34: On cancellation, whatever has been invoiced but not paid is credited: a fully unpaid invoice in full, a partly paid one by a credit note for exactly its unpaid remainder, reconciled with it. Lines not yet invoiced are cancelled, and the unit becomes available again. After cancellation every line shows cancelled — set by the module, not read from accounting, where a credited invoice shows as paid.") |
| T14 | `make test`, `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: round each daily amount to piastres → T2 fails (3,619.80).
- N2: count days from the end of grace → T2 and T5 fail.
- N3: add tonight's fee to the stored value instead of overwriting → T8 fails.
- N4: store the accrued fee in a `Monetary` field → T5 fails (unrounded value lost).
- N5: drop the "unbilled only" rule in billing → T10 fails (second invoice).

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/05-late-fees
make test ARGS="--http-port 8097 --gevent-port 8098"   # T1–T12 + the 52 earlier tests, log clean
make lint                                              # pre-commit green
make test-ci                                           # same tests in the CI Docker stack
make run ARGS="-u real_estate_eg"                      # Step 10 walk-through on re_dev; log clean
gh pr checks                                           # pre-commit + test green on the PR
gh run list --branch main --limit 1                    # green after merge
```

## Done Criteria

- [x] **[AC-05.1](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.1: Given an installment of 241,313 due 10 Apr 2027 and unpaid, on 15 Apr and on 17 Apr (due date + 7) it is not overdue; on 18 Apr it is overdue.")** 241,313 due 10 Apr 2027, unpaid: not overdue on 15 and 17 Apr, overdue on
  18 Apr. *Proof:* T4.
- [x] **[AC-05.2](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.2: Given the same line is paid in full on 25 May 2027 (45 days after due date), its total accrued late fee is 3,619.695, shown as 3,619.70 → billed as 3,620 EGP.")** Paid in full on 25 May 2027: accrued fee 3,619.695, shown 3,619.70, billed
  3,620. *Proof:* T2, T5, T10.
- [x] **[AC-05.3](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.3: Given 141,313 is paid on 30 Apr and 100,000 on 25 May, the accrued fee is 20 days on 241,313 plus 25 days on 100,000 = 2,442.09 → billed as 2,442.")** 141,313 paid 30 Apr and 100,000 on 25 May: fee 2,442.09, billed 2,442.
  *Proof:* T2, T5.
- [x] **[AC-05.4](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.4: Running the nightly job twice on the same day gives the same totals as running it once. Skipping a night and running the next day gives the same totals as running both nights. A payment entered late with an earlier date gives the fee it would have had if entered on time.")** Running the job twice, skipping a night, or a late-entered payment with an
  earlier date all give the same fee as one correct computation. *Proof:* T8.
- [x] **[AC-05.5](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.5: A line's accrued fee never exceeds 10% of its amount.")** A line's fee never exceeds 10 % of its amount. *Proof:* T2, T6.
- [x] **[AC-05.6](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.6: Given a line becomes 61 days past due, its contract is flagged at risk; the contract is not cancelled.")** 61 days past due → contract at risk, not cancelled. *Proof:* T9.
- [x] **[AC-05.7](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.7: When a collections officer or sales manager bills late fees on a contract, one invoice is created for all unbilled fees, its total rounded once; billing again immediately creates nothing.")** A collections officer or manager bills all unbilled fees as one invoice,
  rounded once; billing again creates nothing. *Proof:* T10.
- [x] **[AC-05.8](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.8: The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one.")** The AC-05.2 fee is 3,619.70, not 3,619.80. *Proof:* T2, T5.
- [x] **[AC-05.9](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.9: A late-fee invoice that is itself paid late accrues no late fee.")** A late-fee invoice paid late accrues no fee. *Proof:* T11.
- [x] **[AC-05.10](../../../../docs/business-requirements.md#us-05--flag-overdue-lines-and-accrue-late-fees-every-night "AC-05.10: Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.")** Dated 10 Jan, confirmed 30 Jan 2027: down payment's effective due date 30
  Jan, no fee for 10–29 Jan, not overdue on 6 Feb. *Proof:* T2, T7.
