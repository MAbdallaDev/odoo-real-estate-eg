# Story intake — 09-post-dated-cheques

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `09-post-dated-cheques`

---

## Title

Post-dated cheques (stretch)

---

## Description

Record the post-dated cheques (شيكات آجلة) a buyer hands over and track each one: held, deposited,
cleared or bounced. Each cheque is its own record linked to one schedule line, so a bounced cheque
can be replaced while its history stays. Cheque status is information only — it never changes a
line's payment status, overdue flag or late fees; accounting alone decides those.

**Stretch story:** if time runs short, it moves to v1.1 and Story 10 ships without it.

---

## Acceptance criteria

### User stories

**US-13 — Track post-dated cheques *(stretch)***
*As a **collections officer**, I want to record the cheques a buyer hands over and track each one, so
that I know which to deposit today and which have bounced.*

### Business rules

| ID | Rule |
|---|---|
| BR-40 | A **post-dated cheque** is its own record, linked to one schedule line: cheque number, bank, cheque date, amount and status. A line can have several cheques over time, because a bounced cheque is replaced, so the history is kept. |
| BR-41 | Cheque states: **held → deposited → cleared** or **bounced**. No other transitions. A bounced cheque can be replaced by a new held cheque on the same line. |
| BR-42 | Cheque status is **information only**. It never changes whether a line is paid, overdue or accruing late fees — BR-24 alone decides that. v1 creates no accounting entries for cheques. |
| BR-35 | A **sales agent** sees only contracts where they are the agent, and their schedules, and edits them only while draft. A **sales manager** sees and edits all contracts, bills late fees and records cheques. A **collections officer** reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An **accountant** reads all contracts and schedules and edits none. Agents see the cheques on their own contracts. |

### Acceptance criteria (from the business document)

- **AC-13.1** Given a confirmed or delivered contract, the officer records a cheque (number, bank, date, amount)
  against a schedule line; it starts **held**.
- **AC-13.2** A cheque moves held → deposited → cleared or bounced; any other change is refused.
- **AC-13.3** When a cheque bounces, a new cheque can be recorded on the same line; the bounced one
  stays in the line's history.
- **AC-13.4** Marking a cheque cleared does not change the line's payment status; only a payment in
  accounting does.
- **AC-13.5** A "To deposit" list shows held cheques dated today or earlier.

### Reference data (test fixtures)

**Rights matrix (v1).** R = read, W = create/edit, — = none. Collections officers bill late fees
through the module's billing action, which creates the invoice itself; they get no general invoicing
rights.

| | Agent | Manager | Collections | Accountant |
|---|---|---|---|---|
| Projects, units, plan templates | R | W | R | R |
| Own contracts | W (draft only) | W | R | R |
| Others' contracts | — | W | R | R |
| Confirm / deliver / cancel confirmed | — | W | — | — |
| Schedule lines | W (draft, own) | W | R | R |
| Bill late fees | — | W | W | — |
| Post-dated cheques | R (own) | W | W | R |

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** 04-accounting-link, 07-collections-performance
- **Depends on code areas or other stories:** Story 04 (schedule lines on confirmed contracts), Story 07 (collections menu to put the list in).

## Extra notes (optional)

This is the most Egypt-specific feature in the module, which is why it is in v1 at all.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- Model e.g. `real.estate.cheque` with `line_id`, number, bank, cheque date, amount, state; inherit `mail.thread` so state changes are logged.
- State changes through buttons that check the allowed transition (BR-41); no editable state field.
- Record rules: agents see cheques on their own contracts; reuse the Story 06 pattern.
- "To deposit" list: held cheques with cheque date ≤ today.

## Out of scope

- Cheque journals, entries on deposit or bounce, bounced-cheque fees (Chapter 7).
- Bank integration or reading bank statements.
