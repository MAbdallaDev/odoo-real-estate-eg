# 04 — Accounting link: invoices, payment state, closing and cancellation money

Plan: [`.squad/plans/installments/04-accounting-link/plan.md`](../../.squad/plans/installments/04-accounting-link/plan.md)

Story 04 connects the payment schedule to Odoo Accounting. Each schedule line gets its own
customer invoice when it falls due. The line reads its payment state back from accounting.
A delivered contract closes when everything is paid. Cancelling a confirmed contract records
the retention and the refundable amount, then credits whatever is still unpaid.

## What was added

| Piece | Holds | Rules |
|---|---|---|
| `res.company` *(extended)* + Settings → Real Estate | customer advances account, maintenance deposits account, retention % (15), invoice lead days (0) | BR-22, BR-23, BR-33, BR-43 |
| `data/product_data.xml` | three service products — Down Payment, Installment, Maintenance Deposit — with no taxes | BR-44 |
| `real.estate.installment` *(extended)* | `invoice_id` (accounting users only), `invoice_date`, `date_effective_due`, `state`, `amount_paid`, `amount_residual`; `_create_invoices()`, `_credit_unpaid()` | BR-22 – BR-26, BR-34, BR-43, BR-44 |
| `real.estate.contract` *(extended)* | `amount_paid`, `amount_outstanding`, `retention_amount`, `refundable_amount`; invoicing at confirmation and delivery; `_cron_nightly()` | BR-12, BR-18, BR-21, BR-33, BR-34 |
| `data/ir_cron_data.xml` | "Real Estate: nightly run", daily, as the superuser | §5.5 |

## The journal entries

| Event | Debit | Credit |
|---|---|---|
| Down payment or installment invoiced | Receivable | Customer Advances (liability) |
| Maintenance deposit invoiced | Receivable | Maintenance Deposits (liability) |
| Payment registered | Outstanding Receipts | Receivable — matched with the invoice |
| Cancellation, unpaid amount credited | Customer Advances (or Maintenance Deposits) | Receivable — matched with the invoice |

There is no revenue line in v1 (BR-43). Until the unit is handed over, money received is an
advance that still belongs to the customer. Moving it to revenue at delivery is v1.1.

## One invoice per line

Odoo can put many due dates on one invoice with a payment term. That is not used here.
Late fees (Story 05), partial payments and cheques all work line by line, so each line gets
its own `out_invoice`, posted at once.

- **Idempotent (BR-25).** Only lines with no `invoice_id` are invoiced. The selection
  (`_invoice_due_lines`) and `_create_invoices` both check this, so running the job twice, or
  confirming while the job runs, makes no second invoice.
- **When.** At confirmation, every line already due is invoiced (BR-21). After that, the
  nightly job invoices each line on its due date, or N lead days earlier (BR-22). On delivery,
  the deposit "due at delivery" gets the delivery date and is invoiced (BR-18).
- **Effective due date (BR-26).** The invoice falls due on the later of the line's due date
  and the invoice date. A contract confirmed late is never "late" for the time before it was
  confirmed. Lead days invoice early but keep the scheduled due date.
- **No tax (BR-44).** `account.move.line._compute_tax_ids()` fills taxes from the product
  and the account. The products have none, and the invoice line sends `tax_ids` empty on
  purpose, so a default sales tax set later still does not apply.

## Payment state comes from accounting (BR-24)

A line stores `state`, `amount_paid` and `amount_residual`, computed from its invoice
(`payment_state`, `amount_residual`). They are stored, so agents and collections officers read
them without any right on invoices. Only accounting users see `invoice_id`.

- **`in_payment` counts as paid.** In Community, a registered payment gives `paid`. With the
  Accountant app, the same invoice shows `in_payment` until the bank statement is matched.
  Both mean the customer paid. The test patches `_get_invoice_in_payment_state()` the way
  Odoo's own tests do.
- **The Outstanding Receipts trap.** A payment gets a journal entry only if the bank journal's
  incoming payment method has an Outstanding Receipts account. Without it, the invoice's
  `amount_residual` does not drop, and nothing ever shows paid. The test base
  (`AccountTestInvoicingCommon`) sets it; on a real database it must be checked.
- **Outstanding** on the contract means invoiced but not paid. Future installments that are
  not invoiced yet are not owed yet.

## Superuser and the BR-19 lock

Sales managers and the cron are not accountants. Invoices and credit notes are created with
`sudo()` inside the module's own methods, never through Odoo's wizards. The schedule lock
(BR-19) refuses any change to a confirmed contract's lines, except for the superuser. That is
how the module links invoices and dates the deposit on a locked schedule.

## Closing (BR-12)

Step 4 of the nightly job closes **delivered** contracts whose lines are all `paid`. A line
not yet invoiced is not paid, so a contract with future installments never closes early.
A confirmed contract never closes, even when fully paid (AC-12.2). Story 05 will add "no
unpaid or unbilled late fee" to the condition.

## Cancellation money (BR-33, BR-34)

In this order:

1. **Retention and refundable amount first.** Retention = 15 % of what was paid against the
   down payment and installments, half up to whole EGP. Refundable = that paid amount −
   retention + any paid maintenance deposit. Example E: 1,823,252 paid gives 273,488 and
   1,549,764. Both are stored on the contract; issuing the refund is the accountant's step.
2. **Then the credit notes.** A credit note lowers `amount_residual` exactly like a payment.
   Two guards keep it from counting as money received: the amounts are stored *before* the
   credit notes exist, and the line's `amount_paid` subtracts credit notes
   (`reversal_move_ids`).
3. **One credit note per unpaid invoice, for exactly its residual.** Odoo's reversal wizard
   always credits the whole invoice, which would "refund" money the customer did pay. Here
   each `out_refund` is for `amount_residual`, linked with `reversed_entry_id`, posted and
   matched with the invoice on the receivable account. One path covers both cases: an unpaid
   invoice is credited in full, a partly paid one for its remainder.
4. **Then the contract is cancelled.** Every line shows `cancelled`, set by the module and not
   read from accounting, where a credited invoice shows *Paid* or *Reversed*. The unit is
   available again (BR-03).

## ADR: `l10n_eg` is not a dependency

**Context.** Odoo ships an Egyptian chart of accounts, `l10n_eg`. The module needs two
liability accounts (customer advances, maintenance deposits) and Odoo's receivable and
bank accounts.

**Decision.** `l10n_eg` is **not** in `depends`. The two accounts are company settings
(Settings → Real Estate), picked from whatever chart the company uses, and confirmation is
refused until they are set. The README recommends installing `l10n_eg` for Egyptian
companies.

**Why.**
- A hard dependency would force the Egyptian chart on every company of the database,
  including a holding or a foreign sister company.
- The tests run on Odoo's generic test chart (`AccountTestInvoicingCommon`), as Odoo's own
  modules do, and need no localisation.
- Account codes differ between charts and change between versions; a setting does not depend
  on them.

**Cost.** One setup step: create or pick the two accounts. The confirmation check names the
missing setting, so the step cannot be forgotten.

## Tests

52 tests. The test base is now `AccountTestInvoicingCommon`: a company with a chart of
accounts and a bank journal with Outstanding Receipts. It switches `cls.env` to its own user
and company inside `super().setUpClass()`, so every fixture is created after that call, and
the setup user gets the Real Estate manager group (`get_default_groups()`). Story 04 adds T1–T6
(settings, invoicing, the job), T8–T9 (payment state, totals), T10–T12 (delivery, closing),
T13–T14 (retention, credit notes), plus two checks for refused cases (no invoice before
confirmation, no confirmation without the accounts). "Today" is fixed with `freeze_time`.

**The gates were seen failing** (each change undone before committing):

| Check | Change | Result |
|---|---|---|
| N1 | invoice line without the empty `tax_ids` | T4 fails: the company tax is added |
| N2 | no "no invoice yet" filter, in the selection and in `_create_invoices` | T6 fails: 3 invoices instead of 2 (T2 too) |
| N3 | only `paid`, not `in_payment`, counts as paid | T8 fails |
| N4 | credit notes counted in a line's `amount_paid` | T13 and T14 fail |
| N5 | closing confirmed contracts too | T12 fails |
| N6 | no Outstanding Receipts on the bank journal | T8 fails: the payment does not lower the amount due |

N2 first passed: T6 counted lines that have an invoice, and a duplicate only replaced the
link. T6 now counts the invoices in accounting.

## Open questions

- **Late fees and the closing rule.** Closing will also need "no billed late fee unpaid and
  none left unbilled" (Story 05).
- **Refund payment.** The refundable amount is recorded, not paid; the accountant issues it
  by hand (BR-33).
- **Removing an account after confirmation.** The nightly job then raises the same "set the
  account" error, logged by the scheduler, instead of posting to a wrong account.

## Alternatives considered

- **One invoice with a multi-date payment term** — see "One invoice per line".
- **Odoo's reversal wizard on cancellation** — credits the full invoice; a partly paid one
  would be over-credited.
- **Reading `invoice_id.payment_state` live, unstored** — agents have no rights on invoices,
  and Story 05 and 07 search and group by line state.
- **`l10n_eg` in `depends`** — see the ADR.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-04--accounting-link-invoices-payment-state-closing-and-cancellation-money).

1. Write the journal entries for the down payment of Example A: when it is invoiced, when it
   is paid, and when the contract is cancelled with it still unpaid. Why is there no revenue
   line, and which setting on the bank journal must exist for the payment to make the line
   show paid?
2. Why does the module make its own credit note for exactly the unpaid amount instead of using
   Odoo's reversal wizard? And why must the retention be computed before the credit notes are
   posted — what would a credit note do to `amount_residual`?
3. Why is `invoice_id` visible only to accounting users while `state`, `amount_paid` and
   `amount_residual` are stored on the line? And why do the invoicing methods run with
   `sudo()` — which two things would stop a sales manager otherwise?
