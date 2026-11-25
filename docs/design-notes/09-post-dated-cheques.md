# 09 — Post-dated cheques

Plan: [`.squad/plans/installments/09-post-dated-cheques/plan.md`](../../.squad/plans/installments/09-post-dated-cheques/plan.md)

In Egypt a buyer usually hands the developer a stack of post-dated cheques (شيكات آجلة) at
signing, one for each installment. Collections work is then largely tracking each cheque:
which are in the drawer, which to take to the bank today, which cleared and which bounced.
Story 09 records those cheques and their status (US-13). It was a stretch story; the
maintainer pulled it into v1 before Story 10.

Cheque status is **information only** (BR-42). It never changes whether a line is paid,
overdue or accruing late fees, and it creates no journal entry. Cheque accounting (journals
for cheques under collection, entries on deposit and bounce) stays beyond v1.

## What was added

| Piece | Where | Rules |
|---|---|---|
| `real.estate.cheque`: number, bank, cheque date, amount, schedule line, status; chatter | `models/real_estate_cheque.py` | BR-40 |
| The line's cheque history (`cheque_ids`, read only) | `models/real_estate_installment.py` | BR-40 |
| Moves held → deposited → cleared or bounced, checked in `write()` | `models/real_estate_cheque.py` | BR-41 |
| Access rights (no delete for anyone) and record rules | `security/` | BR-35 |
| Cheque list, form, search; **Cheques** and **Cheques to Deposit** under Collections | `views/real_estate_cheque_views.xml`, `views/real_estate_menus.xml` | AC-13.5 |
| A **Cheques** button on the contract form | `models/real_estate_contract.py`, `views/real_estate_contract_views.xml` | BR-35 |

## A cheque is its own record

A cheque could have been a few fields on the schedule line (number, bank, status). That
breaks on the first bounce: the officer records the replacement cheque and the bounced one
is gone. As its own record linked to one line (BR-40), a line can have several cheques over
time, and a bounced one stays in the line's history next to its replacement (AC-13.3).

- `line_id` is `ondelete="restrict"`: a line with cheques cannot be deleted. Cheques exist
  only on confirmed or delivered contracts, whose schedule is locked anyway (BR-19).
- `contract_id` is a **stored** related field. The agent record rule, the grouping by
  contract and the contract's button all read it.
- The bank is plain text, not a link to `res.bank`. In Odoo's base access rights,
  `group_user` may only read `res.bank`; adding one needs `group_partner_manager`, which a
  collections officer does not have. So an officer could not record a cheque from a bank
  that is not in the list yet.
- Nobody deletes a cheque: no access right has `perm_unlink`. A typo on a held cheque is
  corrected by editing it.

## The state machine lives in `write()`

```python
TRANSITIONS = {
    "held": ("deposited",),
    "deposited": ("cleared", "bounced"),
}
```

`write()` compares every state change with this table and raises `UserError` otherwise
(BR-41, AC-13.2). It does so for every caller: the form's buttons, RPC, an import, other
code, and **the superuser too**. Hiding buttons by state only helps the user; the buttons
just call `write()` with the next state. The state field is also read only in the form.

- A cheque the bank has not seen cannot clear or bounce, so held → cleared and held →
  bounced are refused.
- Cleared and bounced are final. A bounced cheque is replaced, not reopened.
- Once a cheque leaves "held", its number, bank, date, amount and line are history: `write()`
  refuses to change them.
- `create()` always starts a cheque **held**, whatever `state` the values carry, and refuses
  a line whose contract is not confirmed or delivered (AC-13.1).

Each state change is logged in the chatter (`tracking=True` on a `mail.thread` model).

## Why a cleared cheque does not pay the line

A line's payment state is a stored compute that reads the invoice (BR-24). Its
`@api.depends` lists invoice fields only, so nothing about a cheque can trigger it. The
same holds for `is_overdue`, `days_past_due` and the late fee, which the nightly job computes
from the payment history in accounting.

This is deliberate. "Cleared" is what the officer heard from the bank; "paid" is what
accounting recorded. If both could mark a line paid, the two would disagree as soon as one
of them was wrong, and the late fee would be computed from the wrong one. So the accountant
still registers the payment when the money arrives, and that payment pays the line.

T6 proves it against a twin: two identical contracts, cheques on one only (one cleared, one
bounced), the nightly job run on both. Every payment and late-fee field of the two lines is
equal, no journal entry is created, and only a real payment then pays the line.

## Who sees what

| | Agent | Manager | Collections | Accountant |
|---|---|---|---|---|
| Access rights (read, write, create, delete) | R | R W C | R W C | R |
| Record rule | own contracts: `contract_id.user_id = user.id` | through collections | all | all, read only |

The manager group implies both the agent and the collections groups. Group rules are OR-ed
(`_compute_domain()` in `odoo/addons/base/models/ir_rule.py`), so for a manager the agent
rule OR the collections rule gives every cheque. Story 06 needed a separate "manager sees
all" rule for contracts; here the collections rule already covers the manager.

Agents have no Collections menu. They see the cheques on their own contracts through the
**Cheques** button on the contract form. Its count uses `_read_group()` as the current user,
so it follows the same record rules.

## "Today" in the To Deposit list

The To Deposit action's domain is `[('state', '=', 'held'), ('date', '<=', 'today')]`.
`'today'` is a relative date (`parse_date()` in `odoo/tools/date_utils.py`), turned into a
date on the server for `<=` (`_optimize_type_date_relative()` in `odoo/orm/domains.py`), in
the user's timezone. The test reads the action's own domain under `freeze_time`, so it tests
the list the officer opens, not a copy of it.

## Tests

`tests/test_cheques.py`, every check run as an agent, the manager, the collections officer
or the accountant (one `sudo()` write on purpose, to show the superuser is refused too).

| # | Test | Proves |
|---|---|---|
| T1 | Collections and the manager record cheques on a confirmed and a delivered contract; a cheque starts held even if `state` says otherwise | AC-13.1, BR-40 |
| T2 | Refused on a draft and a cancelled contract; amount 0 refused by the database | AC-13.1 |
| T3 | held → deposited → cleared, and → bounced; each move in the chatter | AC-13.2, BR-41 |
| T4 | Every other move refused, by `write()` (manager and superuser) and by the button; a deposited cheque's amount is fixed | AC-13.2, BR-41 |
| T5 | A bounced cheque is replaced on the same line; both stay; nobody can delete one | AC-13.3, BR-40 |
| T6 | A cleared or bounced cheque leaves the line exactly like a twin line with no cheque; no journal entry | AC-13.4, BR-42 |
| T7 | To Deposit holds held cheques dated yesterday and today, not tomorrow's, not deposited or bounced ones | AC-13.5 |
| T8 | Agent A sees their own contract's cheques, agent B none; agents and the accountant change nothing; the contract's count follows the rules | BR-35 |

98 tests pass (90 before this story), with a clean log, locally and in the CI image.

**Negative checks** (each seen failing, then undone before `git add`):

| # | Change | Result |
|---|---|---|
| N1 | Allow held → cleared in `TRANSITIONS` | T4 fails |
| N2 | `_compute_payment()` marks a line paid when it has a cleared cheque (`cheque_ids.state` added to its depends) | T6 fails: the line says `paid`, its twin `invoiced` |
| N3 | No contract-state check in `create()` | T2 fails |
| N4 | Agent rule `[(1, '=', 1)]` | T8 fails |

**A testing trap.** Odoo's test base runs with chatter tracking off (`tracking_disable`,
`mail_notrack` in `odoo/addons/base/tests/common.py`). Turning it back on for one call is
not enough: a record created with tracking off is marked "do not track" until the next
flush (`_track_discard()` in `mail.thread.create()`), and tracking compares a value before
and after a flush. The test flushes before and after each move.

**Manual check (M1)** on `re_dev`, as the collections user: a cheque dated today is in To
Deposit; it is deposited and bounced; a replacement is recorded, deposited and cleared; the
line stays `scheduled`; a backward move is refused; the contract's agent counts 2 cheques.

## Alternatives considered

- **Cheque fields on the schedule line.** Simpler, but a bounce would overwrite the history
  (BR-40).
- **Odoo's payment with a "cheque" method** (`account.payment`). That is cheque
  *accounting*: it posts entries and pays the invoice when the cheque is registered, which
  is what BR-42 rules out for v1. Chapter 7 of the business requirements keeps it for later.
- **A held → bounced move** (a cheque refused before deposit). Not in BR-41; a cheque the
  bank never saw cannot bounce.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-09--post-dated-cheques).

1. Why is the state machine checked in `write()` and not only by showing each button in the
   right state? Name two ways a state could change without anyone clicking a button.
2. The collections officer marks a cheque **cleared**. Why does the schedule line still show
   "Invoiced", and what must happen for it to show "Paid"? Use BR-24 and BR-42.
3. A sales manager sees every cheque, but there is no "manager sees all" cheque rule like
   Story 06 has for contracts. Why is it not needed here?
