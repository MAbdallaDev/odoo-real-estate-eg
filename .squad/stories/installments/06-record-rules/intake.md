# Story intake — 06-record-rules

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `06-record-rules`

---

## Title

Record rules: agents see their own contracts; multi-company

---

## Description

Groups and access rights exist since Story 02. This story adds the record rules: a sales agent sees
only contracts where they are the agent — and those contracts' schedule lines — while managers,
collections officers and accountants see all. It also adds the standard multi-company rule on
`company_id` for every model, so a user only sees data of the companies they are allowed in.

**The maintainer writes the agent record rule and its test personally.** The plan leaves that rule
and its test as a clearly marked task, test first.

---

## Acceptance criteria

### User stories

**US-06 — Agents see only their own contracts**
*As a **sales manager**, I want each agent to see only their own contracts while I see all, so that
customer data and deals stay with the person responsible.*

### Business rules

| ID | Rule |
|---|---|
| BR-35 | A **sales agent** sees only contracts where they are the agent, and their schedules, and edits them only while draft. A **sales manager** sees and edits all contracts, bills late fees and records cheques. A **collections officer** reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An **accountant** reads all contracts and schedules and edits none. Agents see the cheques on their own contracts. |
| BR-36 | Users only see data of the companies they are allowed in. |

### Acceptance criteria (from the business document)

- **AC-06.1** Given agent A owns contract X, when agent B opens the contracts list, X is not there,
  and opening X directly gives an access error.
- **AC-06.2** A manager sees contracts of every agent.
- **AC-06.3** A collections officer sees all contracts but cannot edit price, plan or schedule.
- **AC-06.4** A user allowed only in company 2 cannot see company 1's contracts or units.
- **AC-06.5** An accountant sees all contracts and schedules but cannot edit them.

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

- **Blocked by / related ids:** 05-late-fees
- **Depends on code areas or other stories:** Story 02 (groups, ACLs); Stories 03–05 (every model the rules must cover exists).

## Extra notes (optional)

AC-06.3 and AC-06.5 were met by access rights in Story 02; this story re-runs them with the record rules active to prove nothing regressed.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- `ir.rule` records in `security/`; the agent rule's domain compares the contract's agent field with the current user.
- Schedule lines inherit visibility through their contract (a rule on the line model using the contract's agent).
- Multi-company: the standard `company_id in company_ids` rule pattern — copy the exact domain from a core module's security file rather than writing it from memory.
- Check every `sudo()` added in Stories 02–05 still makes sense with the rules on; each one gets a comment saying why.
- Test: agent B browsing agent A's contract raises `AccessError`; listing contracts as B does not return it.

## Out of scope

- Portal access for customers (Chapter 7).
- Field-level changes to the rights matrix (decided in Story 02).
