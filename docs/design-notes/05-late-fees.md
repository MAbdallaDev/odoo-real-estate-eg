# 05 — Overdue lines, late fees and the at-risk flag

Plan: [`.squad/plans/installments/05-late-fees/plan.md`](../../.squad/plans/installments/05-late-fees/plan.md)

Story 05 adds the late-fee engine to the nightly job. Each night, for every invoiced line of
a live contract, the job works out how many days past due the line is, whether it is overdue,
and what late fee it has accrued. A contract with a line more than 60 days past due is
flagged at risk. A collections officer or sales manager bills the unbilled fees as one
invoice. A delivered contract closes only once its late fees are billed and paid.

## What was added

| Piece | Holds | Rules |
|---|---|---|
| `res.company` *(extended)* + Settings → Real Estate → Collections | late fee rate (1 % a month), cap (10 % of the line), late fees account (income), grace period (7 days), at-risk days (60) | BR-26 – BR-28, BR-30, BR-31 |
| `data/product_data.xml` | a fourth service product, Late Fee, no taxes | BR-30 |
| `tools/late_fee.py` | `compute_late_fee()`, `paid_date()`, `days_past_due()`: pure functions, `Decimal` only | BR-26 – BR-29, BR-45 |
| `real.estate.installment` *(extended)* | `days_past_due`, `is_overdue`, `late_fee_accrued` / `late_fee_billed` / `late_fee_unbilled` (unrounded `Float`), `late_fee_display` (`Monetary`), `late_fee_final`; `_payment_history()`, `_recompute_late_fees()`, `_credit_residual()` | BR-24, BR-26 – BR-29, BR-34 |
| `real.estate.contract` *(extended)* | `at_risk`, `late_fee_accrued`, `late_fee_unbilled`, `late_fee_invoice_ids`; `action_bill_late_fees()`, `_cron_late_fees()`, `_late_fees_settled()`, `_credit_unpaid_late_fees()` | BR-12, BR-30, BR-31, BR-34, BR-35 |
| Contract screens | red overdue lines, days past due and fee columns, "Bill Late Fees", "At Risk" ribbon, filters *Overdue* and *At Risk* | US-05 |

## Computed, not added up (BR-29)

The fee for one line is a function of four inputs: its amount, its effective due date, its
payment history and the as-of date.

> fee = min( Σ over days d with effective due ≤ d < end : unpaid(d) × rate ÷ 100 ÷ 30 ,
> cap % × amount )
>
> end = the day the line was fully paid, or the as-of date while it is unpaid;
> unpaid(d) = amount − payments dated on or before d.

The job **overwrites** the stored value every night. It never adds tonight's fee to last
night's. So running the job twice, skipping a night, or a payment entered on 25 May but dated
21 May all give the same answer as one correct computation (AC-05.4, T8). An accumulating
job would get all three wrong: it would charge twice, miss a night, and keep charging for
days that were in fact paid.

`compute_late_fee()` is a pure function, like Story 03's `compute_schedule()`. Its tests (T2)
need no database, and every Example D number is checked there first.

## The day rule

- **From the effective due date** (BR-26): the later of the due date and the invoice date. A
  contract dated 10 Jan and confirmed 30 Jan is invoiced on 30 Jan, so 10–29 Jan cost
  nothing (AC-05.10). Story 04 already stored `date_effective_due`.
- **Up to, but not including, the day the line is fully paid.** Example D: due 10 Apr,
  paid 25 May → 10 Apr – 24 May = 45 days. The as-of day itself is not charged either, so
  "paid today" and "still unpaid today" give the same count.
- **Each day on the amount unpaid that day.** A payment counts from its own accounting date
  (BR-24): 141,313 paid on 30 Apr → from 30 Apr the daily amount is on 100,000.
- **Grace forgives only inside it** (Q6 of the business document). Overdue = unpaid and more
  than 7 days past the effective due date. If the line was never overdue, the fee is 0. Paid
  on day 8 → 0. Paid on day 9 → it was overdue on day 8 → all 9 days, counted from the due
  date and not from the end of grace.

The sum is computed per segment between payment dates (unpaid × days), and multiplied by the
rate only once at the end.

## Rounding once (BR-27, BR-30, BR-45)

| | Value |
|---|---|
| 45 × 241,313 × 1 % ÷ 30 | 3,619.695 (exact) |
| shown (half up to piastres) | 3,619.70 |
| billed (half up to whole EGP) | 3,620 |
| if each day were rounded to 80.44 | 45 × 80.44 = 3,619.80 ✗ |

The accrued and billed fees are stored **unrounded**, in `Float` fields. A `Monetary` field
cannot hold them, because `Monetary.convert_to_cache()` rounds to the currency (piastres)
every time a value is set (`odoo/orm/fields_numeric.py`). That rounding is used on purpose
for display: `late_fee_display` and the contract's totals are `Monetary` computes, so they
round once, half up (`res.currency.round()` → `float_round()`).

Billing sums the lines' unbilled fees as `Decimal(str(x))` and rounds the total once with
`half_up()`. Each line's billed fee is then set to its accrued fee, still unrounded. The
half-piastre is not lost: 3,619.695 is billed, and the invoice shows 3,620.

## Payment history from accounting

`_payment_history()` reads `account.move._get_all_reconciled_invoice_partials()`. It returns
one entry per partial reconciliation on the invoice's receivable line, with the amount and
the other side (`aml`, the payment's journal item), sorted by date. The payment's date is
`aml.date`, its accounting date. Credit notes (`out_refund`) are skipped because they are not
payments (BR-33), and so are exchange-difference lines (the module is EGP only).

Nothing new is stored for payments. Accounting stays the only record of who paid what and
when, and the fee is derived from it.

## Which lines the job recomputes (§5.5 step 2)

Invoiced lines of confirmed or delivered contracts that are **not paid**, or that were paid
since their fee was last computed. `late_fee_final` marks a line whose fee was computed after
it was fully paid. Such a line can never change again, so it is skipped. If a payment is
later unreconciled, the line is no longer `paid`, so it is picked up again.

## Overdue and at risk: stored computes on the line state

`days_past_due` is written by the job, because it depends on the date. `is_overdue` and the
contract's `at_risk` are **stored computes** on the line state and on `days_past_due`. So
registering a payment clears both at once, with no need to wait for the next night. Both
fields are stored, so they can be searched (the *Overdue* and *At Risk* filters, and Story
07's screens). `at_risk` is tracked in the chatter. Nothing ever cancels a contract (BR-31).

## Billing (BR-30, BR-35)

| User | Bill Late Fees |
|---|---|
| Collections officer | yes |
| Sales manager | yes (the group implies collections) |
| Sales agent | `AccessError` |
| Accountant | `AccessError` |

Collections officers have no invoicing rights. So the action checks the group, then creates
and posts the invoice with `sudo()` inside the module's own method. A chatter note gives the
amount and the invoice number to users who cannot open invoices. A second click finds
nothing unbilled and creates nothing (AC-05.7). A total under 0.50 EGP rounds to 0 and is not
billed.

Late-fee invoices are linked to the contract (`late_fee_invoice_ids`, accounting users only)
and are **not schedule lines**. The job never reads them, so they never accrue a fee and
never make a contract at risk (AC-05.9).

## The journal entries

Example D, paid in full on 25 May; fees billed on 26 May (Late Fees = an *Other Income*
account):

| When | Debit | Credit |
|---|---|---|
| Late-fee invoice posted | Accounts Receivable 3,620 | Late Fees (income) 3,620 |
| Customer pays it | Outstanding Receipts 3,620 | Accounts Receivable 3,620 |
| Contract cancelled with it unpaid (credit note) | Late Fees (income) 3,620 | Accounts Receivable 3,620 |

Late fees are income the developer earns, not customer money it holds. That is why they
post to an income account, unlike the advances and the deposit. They carry no tax for now:
BR-44 covers schedule lines only, so this needs a tax advisor (open question).

## Closing and cancellation

- **Closing (BR-12).** A delivered contract with every line paid now also needs every
  late-fee invoice paid and nothing left to bill (`_late_fees_settled()`). T12: it stays
  delivered while a fee is unbilled, stays delivered while the fee invoice is unpaid, then
  closes.
- **Cancellation (BR-34).** Unpaid late-fee invoices are credited for their remainder, by the
  same code as schedule lines (`_credit_residual()`, split out of Story 04's
  `_credit_unpaid()`), to the account each was billed to. Paid late fees are not refunded
  (BR-33), and retention counts only the down payment and installments. Fees never billed
  are dropped: a cancelled contract is no longer computed.

## Tests

72 tests (20 new). T2 (`test_late_fee_math.py`) checks the arithmetic with no database. T1
and T3–T11 (`test_late_fees.py`) run the real job, payments and billing. T12 is in
`test_delivery_closing.py` and T13 in `test_cancellation.py`. Payments go through Odoo's
register-payment wizard with an explicit `payment_date`. The job is called with an explicit
date under `freeze_time`. Odoo's `odoo/tests/common.py` replaces `freezegun.freeze_time` with
its own class, so `from freezegun import freeze_time` gets Odoo's version.

**The gates were seen failing** (each change undone before committing):

| Check | Change | Result |
|---|---|---|
| N1 | round each daily amount to piastres | 10 tests fail: T2 (3,619.80 instead of 3,619.70; the cap, grace and two-part cases), T5, T8, T10, T11 |
| N2 | count days from the end of grace | 14 tests fail: T2, T5, T7, T8, T10–T13 (fees too low by 7 days) |
| N3 | add tonight's fee to the stored value | T8 fails (a second run the same night doubles the fee); T5 two-part case too |
| N4 | `late_fee_accrued` as a `Monetary` field | T5, T8, T10, T11 fail: 3,619.70 is stored instead of 3,619.695 |
| N5 | bill the accrued fee instead of the unbilled fee | T10 fails: a second click creates a second invoice; T13 too |

## Open questions

- **Tax on late fees.** None in v1. To be confirmed with a tax advisor.
- **Legal rate.** 1 % a month is 12 % a year, above the 7 % cap in Civil Code Art. 227. It
  is a company setting, set with the developer's lawyer (§6.4).
- **Waivers** are Chapter 7. Without them, an unbilled fee keeps a delivered contract open
  until it is billed and paid.

## Alternatives considered

- **Add each night's fee to a running total.** Simple, but not idempotent. A rerun, a skipped
  night or a back-dated payment would all break it (BR-29).
- **Round each daily amount.** Drifts: 3,619.80 instead of 3,619.70 (AC-05.8).
- **One invoice line per schedule line on the late-fee invoice.** Each line would be rounded
  to piastres by Odoo, so the total would no longer be rounded once.
- **Grace and at-risk days as code constants.** Rejected in review: they are in the same §6.4
  policy table as the rate and cap, and a developer may want other values.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-05--overdue-lines-late-fees-and-the-at-risk-flag).

1. Example D, paid in two parts (141,313 on 30 Apr, 100,000 on 25 May): which days are
   charged, on which amount, and why is the result 2,442.09 shown and 2,442 billed? What
   would change if the line had been paid in full on 18 Apr instead, and on 19 Apr?
2. Why is the fee recomputed from the payment history every night instead of adding one
   day's fee to the stored value? Give the three cases from AC-05.4 and say what an
   accumulating job would get wrong in each.
3. Why are `late_fee_accrued` and `late_fee_billed` plain `Float` fields while the totals on
   the screen are `Monetary`? And why can a collections officer bill late fees without any
   invoicing rights — what does the action do to make that safe?
