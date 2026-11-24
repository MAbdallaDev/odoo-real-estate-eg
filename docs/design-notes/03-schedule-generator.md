# 03 — Payment plan templates and the schedule generator

Plan: [`.squad/plans/installments/03-schedule-generator/plan.md`](../../.squad/plans/installments/03-schedule-generator/plan.md)

Story 03 turns a contract into a payment schedule. A sales manager defines payment plan
templates; an agent picks one on a draft contract and the schedule is generated: a down
payment, N installments and a separate maintenance deposit line, in whole Egyptian pounds,
summing exactly to the contract price. A manager can no longer confirm a contract without such
a schedule. The story also adds BR-46: one contact per national ID or passport number.

## What was added

| Piece | Holds | Rules |
|---|---|---|
| `real.estate.plan.template` | down payment %, installments, frequency, months to the first installment, maintenance %, deposit due at signing or delivery | BR-14, BR-20 |
| `tools/schedule.py` — `compute_schedule()` | the arithmetic, as a pure function | BR-15 – BR-18, BR-45 |
| `real.estate.installment` | one schedule line: type, number, amount, due date | BR-18, BR-19 |
| `real.estate.contract` *(extended)* | payment plan, schedule lines, schedule total; generate action; schedule check at confirmation | BR-10, BR-19 |
| `real.estate.schedule.generate` *(transient)* | the "pick a plan" dialog | US-02 |
| `res.partner` *(extended)* | national ID and passport number unique across all contacts | BR-46 |

**Who wrote what.** The maintainer wrote the schedule arithmetic — the six lines that round,
split, take the remainder and date each installment — in a skeleton the AI prepared (imports,
loop, line dictionaries). Its tests were written and committed first, so they fixed what
"correct" means before the code existed. Everything around it is AI-written and
maintainer-reviewed.

## The arithmetic: a pure function

`compute_schedule(price, contract_date, plan values...)` returns a list of plain dictionaries.
It knows nothing about the ORM, so it is tested without a database (`BaseCase`, as core tests
pure helpers such as `html_editor`'s diff utilities), and the contract only turns its output
into records.

**Money is `Decimal`, rounded half up once per line (BR-45).** Two traps it avoids:

| Value | Plain Python | Correct |
|---|---|---|
| 8,580,005 × 10 % = 858,000.5 | `round(858000.5)` = **858,000** (round half to *even*) | 858,001 |
| 1,310,730 × 35 % = 458,755.5 | in float, `1310730 * 0.35` = `458755.49999999994`, so even a hand-made "half up" gives **458,755** | 458,756 |

Inputs become `Decimal(str(x))` — never `Decimal(x)` on a float, which copies the float's error.

**The last installment takes the remainder (BR-16).** Each installment is
(price − down payment) ÷ N, rounded; the last one is the rest minus the first N − 1, so down
payment + installments equal the price to the pound. Example A: 7,722,000 ÷ 32 = 241,312.5,
rounded to 241,313; 31 × 241,313 = 7,480,703; the last is 241,297.

**Dates come from the contract date, never from the previous line (BR-17).** Installment *k*
is due `contract_date + relativedelta(months=first + (k − 1) × step)`. `relativedelta` moves a
day past the month's end to its last day, and because every line starts again from the
anchor, day 31 comes back: 31 Jan 2027 gives 28 Feb, 31 Mar, 30 Apr, 31 May — and 29 Feb 2028
for installment 13. Chaining from the previous date would stick at the 28th forever.

## Generating, regenerating, locking

- **The dialog is thin.** The wizard only picks a plan and calls the contract's
  `_generate_schedule(plan)`, so the rules hold whoever calls it. The old lines are deleted
  and the new ones created in one `write()` with `Command.create`.
- **Draft only (BR-19).** Generating is refused once the contract is confirmed, for managers
  too. The lines themselves are locked in `create()`, `write()` and `@api.ondelete`: three
  hooks, because each is a different way to change data. Only the superuser passes — Story 04's
  nightly job will link invoices to lines.
- **No stale schedule.** Changing a draft's unit (so its price) or its contract date deletes
  its lines; confirmation then asks for a new schedule. Only a real change counts: confirmation
  itself writes the date (BR-07 fills an empty one) and must keep the lines.
- **The contract date is locked after confirmation.** Story 02's form already made it
  read-only, but `write()` still let a manager change it through an import or the API, which
  would leave the confirmed schedule's dates behind. Decided in this story: the model refuses
  it, as it already refused a new unit.
- **Read-only roles are refused at the entry point.** `action_generate_schedule()` writes
  nothing — it only opens the dialog — so Odoo would not check access by itself. It calls
  `check_access("write")` (Odoo 19's single call for access rights and record rules), so a
  collections officer calling it over RPC gets an `AccessError` at once. The hidden button is
  only the user interface.
- **Confirmation (BR-10)** now also requires a schedule whose down payment and installments
  equal the price (`currency.compare_amounts`; the deposit is excluded, BR-18). The check runs
  after the date and identity checks, so those are reported first.

## Why our own lines, not Odoo payment terms

Odoo's `account.payment.term` already splits an amount into dated parts
(`_compute_terms()`). It is not used: BR-22 needs **one invoice per line**, each with its own
late fees, partial payments and cheques (Stories 04, 05, 09). Payment terms split one invoice;
our schedule is many lines, each a future invoice.

## One contact per identity number: two layers (BR-46)

Carried over from Story 02's open question. A national ID or passport number belongs to one
contact, across all companies, archived contacts included.

1. **The database:** two partial unique indexes,
   `(national_id) WHERE national_id IS NOT NULL AND national_id != ''` and the same for the
   passport, so two saves at the same moment cannot both pass.
2. **The message:** before `super().create()` / `super().write()`, a search with
   `with_context(active_test=False).sudo()` — the same search Odoo uses to *warn* about a
   duplicate tax ID (`_compute_same_vat_partner_id`) — refuses the save and names the contact
   that has the number.

The first version used `@api.constrains`. It runs *after* the INSERT, so the unique index
refused first, with no contact name; the first test run showed it. A check that must beat a
database constraint goes before `super()`.

## Tests

37 tests, every action run as a user from `new_test_user`. Story 03 adds: T1 (BR-46), T2–T3
(plan templates), T4–T8 (the arithmetic, written before the code), T9–T12 and T17 (generating,
regenerating, stale schedules, refusals), T13 (confirmation needs the schedule), T14 (read-only
roles, extended), T16 (the BR-19 lock). Story 02 tests that confirm a contract now generate a
schedule first (`add_schedule()` in `common.py`).

**The gates were seen failing** (each change undone before committing):

| Check | Change | Result |
|---|---|---|
| N1 | `round()` instead of half up | T4, T5, T8 fail |
| N2 | each date from the previous one | T6 fails: 28 Mar, 28 Apr instead of 31 Mar, 30 Apr |
| N3 | no schedule check at confirmation | T13 fails |
| N4 | BR-46 search without `sudo()` / `active_test=False` | T1 fails on the other-company and archived cases (raw `UniqueViolation`) |
| N5 | no BR-19 lock on lines | T16 fails for agent and manager |
| N6 | no draft check before generating | T11 fails for agent and manager |
| N7 | contract date editable after confirmation | `test_br_35_agent_edits_only_drafts` fails |
| N8 | collections officer given write rights on lines | T14 fails on add, edit and delete line |

The arithmetic tests were also run once against a throwaway correct version before the
maintainer wrote theirs, so a failure could only mean wrong code, not wrong expectations.

## Open questions

- **Maintenance deposit due at delivery.** Its line has no date yet; filling it with the
  delivery date belongs with invoicing (Story 04).
- **BR-07's "empty date becomes the confirmation date"** is now reached only by lines made
  outside the generator: generating needs a date, and confirming needs a schedule. Kept, and
  tested (T16).
- **Passport numbers are compared exactly as typed.** Two countries could issue the same
  number; BR-46 says one contact per number anyway. Normalising (spaces, case) is not done.
- **Editing a plan template** does not change schedules already generated from it: lines are
  a snapshot. Intended; regenerate a draft to apply a changed plan.

## Alternatives considered

- **Odoo payment terms** for the schedule — see above; one invoice per line rules them out.
- **`float_round(..., rounding_method='HALF-UP')`** — allowed by BR-45 and correct; `Decimal`
  was chosen so the whole calculation stays exact, not just the rounding step.
- **A computed, stored schedule** that follows the plan and price automatically — would
  change a schedule the customer has seen; an explicit "generate" with a draft-only rule keeps
  control with the agent.
- **`@api.constrains` for BR-46** — too late, see above; the check sits in `create()` /
  `write()` instead.
- **Keeping the contract date editable after confirmation** — rejected by the maintainer:
  the schedule's dates are counted from it.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-03--payment-plan-templates-and-the-schedule-generator).

1. The schedule uses `Decimal` with `ROUND_HALF_UP`, not `round()` and not plain floats. Give
   one value each would get wrong, and explain how the last installment makes the schedule
   sum exactly to the price.
2. Why is each due date computed from the contract date and not from the previous due date?
   What does 31 Jan 2027 + 1 month give, and what goes wrong for the following months if you
   chain from that result?
3. The BR-46 check first used `@api.constrains` and now runs before `super().create()`. Why
   did the first version never show its message, what does the unique index still add, and why
   does the search use `sudo()` and `active_test=False`?
