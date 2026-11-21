# Story intake — 03-schedule-generator

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `03-schedule-generator`

---

## Title

Payment plan templates and the schedule generator

---

## Description

Add payment plan templates and generate a contract's schedule from one: a down payment, N
installments at a monthly / quarterly / semi-annual / annual step, and a separate maintenance
deposit line. Amounts round to whole EGP half up, the last installment absorbs the rounding
difference, and due dates are always computed from the contract date with month-end clamping.

**The maintainer writes the schedule arithmetic and its rounding personally** — the amounts, the
last-line adjustment and the due-date computation. The plan for this story must leave that code as a
clearly marked task with its tests written first, so the tests define what "correct" means before
the code exists.

---

## Acceptance criteria

### User stories

**US-02 — Generate the payment schedule from a plan**
*As a **sales agent**, I want to pick a plan template and generate the schedule, so that the customer
sees exactly what they will pay and when.*

**US-10 — Confirm a contract**
*As a **sales manager**, I want to approve each contract before it becomes binding, so that no deal is
committed without a check.*

### Business rules

| ID | Rule |
|---|---|
| BR-14 | A **payment plan template** defines: down payment %, number of installments, frequency (monthly, quarterly, semi-annual, annual), months from contract date to the first installment, maintenance deposit %, and when the maintenance deposit is due (**at signing** or **at delivery**). |
| BR-15 | **Down payment** = contract price × down payment %, rounded to whole EGP (half up). Due on the contract date. |
| BR-16 | **Installments**: (contract price − down payment) ÷ number of installments, each rounded to whole EGP (half up). **The last installment absorbs the rounding difference**, so down payment + installments = contract price to the pound. |
| BR-17 | **Due dates** are always computed from the contract date — installment *k* is due *offset + (k−1) × step* months after it — never from the previous due date. A date past the end of a short month moves to that month's last day, without drift: a plan anchored on 31 January falls due on 28 Feb, 31 Mar, 30 Apr, 31 May. |
| BR-18 | The **maintenance deposit** = contract price × maintenance %, rounded to whole EGP (half up). It is a separate schedule line and is **not** part of the contract price. If due at signing, it is due on the contract date; if due at delivery, it has no date until the contract is delivered, then it is due on the delivery date. |
| BR-19 | The schedule can be regenerated only while the contract is draft. Once confirmed, amounts and dates are locked. |
| BR-20 | A plan with 0 installments and 100% down payment is valid (a cash sale). |
| BR-45 | All money arithmetic rounds **half up** with exact decimal arithmetic (`Decimal`, or Odoo's `float_round`, which corrects binary-float error) — never plain `float`. Several test values sit exactly on a rounding tie (e.g. 3,619.695). |

### Acceptance criteria (from the business document)

- **AC-02.1** Given a contract at 8,580,000 on 10 Jan 2027 with plan `NH-STD-8Q`, when the agent
  generates the schedule, then there is a down payment of 858,000 due 10 Jan 2027, 31 installments of
  241,313 and a last installment of **241,297**, quarterly from 10 Apr 2027 to 10 Jan 2035, and a
  maintenance deposit of 686,400 with no due date (due at delivery).
- **AC-02.2** Given any price and plan, down payment + installments = the contract price exactly.
  Tested with 6,712,345 on `NH-STD-8Q`: down payment 671,235, 31 × 188,785, last **188,775**.
- **AC-02.3** Given plan `NH-BIZ-5M` on a contract dated 31 Jan 2027, the first four installments are
  due 28 Feb, 31 Mar, 30 Apr and 31 May 2027.
- **AC-02.4** Given plan `NH-CASH`, the schedule is one down payment of the full price and no
  installments.
- **AC-02.5** Given a draft contract with a schedule, when the agent regenerates it with another plan,
  then the old lines are replaced. Given a confirmed contract, regeneration is refused.
- **AC-10.2** Confirmation is refused if there is no schedule, if the schedule does not sum to the
  price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A
  company customer needs neither.
  *This story:* the schedule check (no schedule, or not summing to the price, blocks confirmation).

### Reference data (test fixtures)

#### 6.3 Payment plan templates

| Code | Name | Down | Installments | Frequency | First installment | Maintenance | Maintenance due |
|---|---|---|---|---|---|---|---|
| `NH-STD-8Q` | Standard 8 years | 10% | 32 | Quarterly | +3 months | 8% | At delivery |
| `NH-EXT-10Q` | Extended 10 years | 5% | 40 | Quarterly | +3 months | 8% | At delivery |
| `NH-SAHEL-7Q` | Sahel 7 years | 10% | 28 | Quarterly | +3 months | 10% | At delivery |
| `NH-BIZ-5M` | Business 5 years | 20% | 60 | Monthly | +1 month | 10% | At signing |
| `NH-CASH` | Cash | 100% | 0 | — | — | 8% | At delivery |

**A — Standard plan.** Unit `HNC-B07-0302`, 3-bedroom, 165 m² × 52,000 = **8,580,000**. Plan
`NH-STD-8Q`, contract date 10 Jan 2027.

| Line | Amount | Due |
|---|---|---|
| Down payment (10%) | 858,000 | 10 Jan 2027 |
| Installments 1–31 | 241,313 each | quarterly, 10 Apr 2027 → 10 Oct 2034 |
| Installment 32 | **241,297** | 10 Jan 2035 |
| **Total of price** | **8,580,000** | |
| Maintenance deposit (8%) | 686,400 | on delivery date |

Exact installment = 7,722,000 ÷ 32 = 241,312.50 → rounded half up to 241,313; 31 × 241,313 =
7,480,703; last = 7,722,000 − 7,480,703 = 241,297.

**B — Ugly rounding.** Price **6,712,345**, plan `NH-STD-8Q`: down payment 671,234.5 → **671,235**;
remainder 6,041,110 ÷ 32 = 188,784.6875 → **188,785** × 31 = 5,852,335; last = **188,775**.
Check: 671,235 + 5,852,335 + 188,775 = 6,712,345.

**C — Month-end dates.** Office `CBP-A02-0105`, 60 m² × 61,000 = **3,660,000**, plan `NH-BIZ-5M`,
contract date **31 Jan 2027**: down payment 732,000 and maintenance deposit 366,000 (at signing) due
31 Jan 2027; 60 installments of 48,800; first four due **28 Feb, 31 Mar, 30 Apr, 31 May 2027**.

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** 02-core-models
- **Depends on code areas or other stories:** Story 02 (contract model and states).

## Extra notes (optional)

Worked examples A, B and C below are the test fixtures, number for number.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- Models: `real.estate.plan.template`, `real.estate.installment` (one row per schedule line, with a line type: down payment / installment / maintenance deposit), and a transient wizard to pick the plan and generate.
- Use `Decimal` with `ROUND_HALF_UP`, or Odoo's `float_round` with half-up rounding — never plain `float` arithmetic (BR-45). B's down payment 671,234.5 is an exact tie.
- Month arithmetic: `dateutil.relativedelta` clamps to month end; always add `offset + (k−1) × step` months to the contract date, never to the previous line.
- Regeneration deletes and recreates lines only in draft (BR-19); confirm must check the sum (BR-10).

## Out of scope

- Invoicing any line (Story 04).
- Late fees (Story 05).
- Discounts or plan-based price changes (Chapter 7).
