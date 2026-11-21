# Story intake — 05-late-fees

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `05-late-fees`

---

## Title

Overdue lines, late fees and the at-risk flag

---

## Description

Add the late-fee engine to the nightly job. A line's effective due date, days past due and overdue
flag follow BR-26. Its accrued late fee is **computed** from the effective due date, its payment
history in accounting and the as-of date — simple interest at the company's monthly rate on the amount
unpaid each day, unrounded per day, capped at 10% of the line — and the job stores the result. Because
it is a computation and not a running total, running twice, skipping a night, or a payment entered
late with an earlier date all give the same answer.

Collections officers and sales managers bill a contract's unbilled fees as one invoice rounded once to
whole EGP. Contracts with a line more than 60 days past due are flagged at risk; nothing is ever
cancelled automatically.

---

## Acceptance criteria

### User stories

**US-05 — Flag overdue lines and accrue late fees every night**
*As a **collections officer**, I want overdue lines flagged and late fees accrued automatically, so
that penalties are applied the same way for every customer.*

### Business rules

| ID | Rule |
|---|---|
| BR-24 | Whether a line is paid, partly paid or unpaid is **read from its invoice in accounting**; nobody types "paid". Amounts come from the invoice's amount due (`amount_residual`); an invoice shown as *In payment* counts as paid. Bank and cash journals use an **outstanding receipts account**, so a registered payment reduces the amount due at once instead of waiting for bank reconciliation (demo data and tests configure this). A payment counts from its own accounting date. |
| BR-26 | A line's **effective due date** is the later of its scheduled due date and its invoice date, so nothing is late for time before the contract was confirmed. **Days past due** = today − effective due date. A line is **overdue** when it is not fully paid and today is **after** effective due date + **grace period** (7 days). |
| BR-27 | Once a line is overdue, a **late fee accrues for every day d from its effective due date up to, but not including, the day it is fully paid** — not from the end of the grace period — on the amount **unpaid on day d** (a payment counts from its own date), at 1% per month (1/30 of 1% per day; a company setting). Simple interest, never compounding. Every schedule line accrues — down payment, installments and maintenance deposit; **late-fee invoices never do**. Daily amounts are **not rounded day by day**: the total is computed from the unrounded daily amounts and rounded once (to piastres for display, to whole EGP when billed). Rounding each day would drift — 45 days on 241,313 gives 3,619.695 (shown 3,619.70) but 3,619.80 if each day were rounded to 80.44. |
| BR-28 | Total late fees on one line are **capped at 10%** of that line's amount. |
| BR-29 | A line's accrued late fee is **computed, not added up night by night**: from its effective due date, its payment history in accounting and the as-of date, then capped (BR-28). The nightly job stores the result. Running it twice, skipping a night, or entering a payment late with an earlier date all give the same answer as one correct computation. |
| BR-30 | Late fees are billed deliberately: a collections officer or sales manager bills a contract's unbilled fees in one invoice. Each line's unbilled fee = accrued − already billed, both kept unrounded; the invoice total is rounded **once** to whole EGP. The system never bills them on its own. |
| BR-31 | A contract with any line more than **60 days past due** is flagged **at risk of cancellation**. The system never cancels a contract on its own. |
| BR-45 | All money arithmetic rounds **half up** with exact decimal arithmetic (`Decimal`, or Odoo's `float_round`, which corrects binary-float error) — never plain `float`. Several test values sit exactly on a rounding tie (e.g. 3,619.695). |

### Acceptance criteria (from the business document)

- **AC-05.1** Given an installment of 241,313 due 10 Apr 2027 and unpaid, on 15 Apr and on 17 Apr
  (due date + 7) it is not overdue; on 18 Apr it is overdue.
- **AC-05.2** Given the same line is paid in full on 25 May 2027 (45 days after due date), its total
  accrued late fee is 3,619.695, shown as **3,619.70** → billed as **3,620** EGP.
- **AC-05.3** Given 141,313 is paid on 30 Apr and 100,000 on 25 May, the accrued fee is 20 days on
  241,313 plus 25 days on 100,000 = **2,442.09** → billed as **2,442**.
- **AC-05.4** Running the nightly job twice on the same day gives the same totals as running it once.
  Skipping a night and running the next day gives the same totals as running both nights. A payment
  entered late with an earlier date gives the fee it would have had if entered on time.
- **AC-05.5** A line's accrued fee never exceeds 10% of its amount.
- **AC-05.6** Given a line becomes 61 days past due, its contract is flagged at risk; the contract is
  not cancelled.
- **AC-05.7** When a collections officer or sales manager bills late fees on a contract, one invoice is created for all
  unbilled fees, its total rounded once; billing again immediately creates nothing.
- **AC-05.8** The fee in AC-05.2 is 3,619.70, not 3,619.80 — daily amounts are not rounded one by one.
- **AC-05.9** A late-fee invoice that is itself paid late accrues no late fee.
- **AC-05.10** Given a contract dated 10 Jan 2027 and confirmed on 30 Jan 2027, its down payment's
  effective due date is 30 Jan 2027; it accrues no fee for 10–29 Jan and is not overdue on 6 Feb.

### Reference data (test fixtures)

#### 5.5 Nightly job, in order

1. Invoice every scheduled line of a confirmed contract whose due date (minus lead days) has arrived
   — once per line (BR-25).
2. For every overdue line, and every line paid since the last run, recompute its accrued late fee
   from its payment history and store it (BR-27–BR-29).
3. Flag contracts with a line more than 60 days past due as at risk; clear the flag when no such line
   remains (BR-31).
4. Close delivered contracts whose lines are all paid and have no unbilled late fee (BR-12).

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

**D — Late fee.** Example A's installment 1 (241,313, due 10 Apr 2027) paid in full on 25 May 2027:
45 days (10 Apr – 24 May) × 241,313 × 1% ÷ 30 = 3,619.695 → shown **3,619.70** → billed **3,620**.
Cap = 24,131.30, not reached. Paid in two parts instead — 141,313 on 30 Apr, 100,000 on 25 May:
20 days on 241,313 (1,608.7533…) + 25 days on 100,000 (833.3333…) = 2,442.0867 → shown **2,442.09**
→ billed **2,442**.

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** 04-accounting-link
- **Depends on code areas or other stories:** Story 04 (invoices, payment state, nightly job).

## Extra notes (optional)

The rate (1% per month) and cap are company settings. 12% a year is above the 7% interest cap in
Egyptian Civil Code Art. 227, so the demo value is illustrative (business document §6.4).

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- Day-count rule: a day d is charged when effective due date ≤ d < the date the line became fully paid (or the as-of date). Check against D: 10 Apr–24 May = 45 days.
- Payment history: the dates and amounts of payments reconciled with the line's invoice; a payment counts from its own accounting date (BR-24).
- Store accrued (unrounded) and billed (unrounded) per line; unbilled = accrued − billed (BR-30).
- Late-fee invoices are not schedule lines and never accrue (AC-05.9).
- Tests freeze "today" (e.g. `freezegun` if Odoo 19 ships it, or pass the as-of date explicitly) — verify what Odoo 19's test tools provide.
- The billing action creates the invoice with controlled elevated rights; collections officers get no general invoicing rights (BR-35).

## Out of scope

- Late-fee waivers (Chapter 7).
- Automatic cancellation (never — BR-31).
- Bounced-cheque fees (Chapter 7).
- Notifications or SMS to customers.
