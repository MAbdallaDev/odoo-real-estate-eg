# 06 — Record rules: agents see their own contracts; multi-company

Plan: [`.squad/plans/installments/06-record-rules/plan.md`](../../.squad/plans/installments/06-record-rules/plan.md)

Story 02 gave each role its **access rights**: which tables it may read, write, create or
delete. Story 06 adds **record rules**: which rows of those tables. A sales agent sees only
contracts where they are the agent, and those contracts' schedule lines. A sales manager, a
collections officer and an accountant see all of them (BR-35). Every model also gets the
standard multi-company rule, so a user sees only the data of the companies they are allowed
in (BR-36).

## What was added

All rules are in `security/ir_rules.xml`, loaded after `ir.model.access.csv`.

| Rule | Models | Groups | Domain | Perms | Rules |
|---|---|---|---|---|---|
| multi-company | project, unit, plan template, contract, schedule line | none (global) | `[('company_id', 'in', company_ids)]` | all | BR-36 |
| agent sees own | contract | Sales Agent | `[('user_id', '=', user.id)]` | all | BR-35 |
| agent sees own | schedule line | Sales Agent | `[('contract_id.user_id', '=', user.id)]` | all | BR-35 |
| manager sees all | contract, schedule line | Sales Manager | `[(1, '=', 1)]` | all | BR-35 |
| read all | contract, schedule line | Collections Officer, Invoicing (accountant) | `[(1, '=', 1)]` | read only | BR-35 |

The agent rule and its test were planned as the maintainer's own task. Claude wrote them at
the maintainer's request.

## How Odoo combines rules

From `odoo/addons/base/models/ir_rule.py`, `_compute_domain()`:

- A rule **without groups** is **global**. Every global rule of the model is AND-ed: each
  one can only narrow what a user sees. The multi-company rules are global, so even a
  manager allowed only in company 2 sees nothing of company 1.
- A rule **with groups** applies only to members of one of its groups. The group rules that
  apply to a user are **OR-ed** together, then AND-ed with the global ones. So a group rule
  can widen what another group rule allows.
- The superuser (`sudo()`, the nightly job) skips record rules completely.
- `perm_read`, `perm_write`, `perm_create`, `perm_unlink` say for which operations a rule
  counts. A rule that is read only is ignored when Odoo checks a write.
- The domain is evaluated with `user` (the current user) and `company_ids` (the companies
  active in the company switcher), from `_eval_context()`.

## Why managers need a "see all" rule

The manager group implies the agent group (Story 02), so a manager is also an agent. Without
a manager rule, the agent rule would apply to them alone, and a manager would see only
contracts where they are the agent. The manager rule `[(1, '=', 1)]` is OR-ed with the agent
rule: own contracts OR every contract = every contract. This is the same pair as Odoo's
`sale_order_personal_rule` and `sale_order_see_all`.

No group was changed: the manager still implies the agent and collections groups.

## Why "read all" is read only

Collections officers and accountants are not agents, so no group rule applies to them and
they would see everything without any rule. The read-only rule matters for a user who is in
both groups, for example an agent who is also an accountant. For a read, the agent rule OR
the read-all rule applies: every contract. For a write, only the agent rule counts: their
own contracts. And the contract's `write()` still allows drafts only. A full "see all" rule
would have let this user edit other agents' drafts.

## Lines follow their contract

A schedule line has no agent of its own. Its rule follows the contract with a dotted path,
`contract_id.user_id`, like Odoo's `sale_order_line_rule_portal` (`order_id.partner_id`).
If the contract gets a new agent, the lines move with it.

## What still works across agents

- **A unit already sold.** `_check_unit_free()` searches as superuser. Agent B cannot see
  agent A's contract, but still gets "Unit … already has contract …" with the reference only
  (BR-04).
- **Stored computed fields.** The unit's state and the contract's at-risk flag are stored
  computes, and Odoo recomputes those as superuser (`compute_sudo` defaults to `store` in
  `odoo/orm/fields.py`). So one agent's contract updates the unit state everyone reads.
- **The nightly job** runs as superuser, across every agent and company.
- **The two wizards** are transient models: Odoo already limits them to the user who opened
  them, and they act on a contract the user must be able to see.

## The `sudo()` audit

Every `sudo()` from Stories 02–05 was read again with the rules on. Each has a one-line
reason next to it. None of them hides a record rule from a user who should not see the data:

| Where | Why |
|---|---|
| `_check_unit_free()` | the unit is taken even if another agent's contract is hidden |
| invoicing, credit notes, late-fee billing | collections officers, managers and the job have no accounting rights; the schedule of a confirmed contract is locked (BR-19) |
| `late_fee_invoice_ids`, `invoice_id` | fields limited to accounting users (`groups=`) |
| `_cron_late_fees()`, `_invoice_due_lines()` | the job covers every contract; `invoice_id` is accounting only |
| `res.partner` duplicate check | as Odoo's duplicate tax ID warning: archived or other-company contacts still count |

The contract report reads the contract as the user, so agent B cannot print agent A's
contract either (tested).

## Tests

`tests/test_record_rules.py` (and one test in `test_report.py`), all as real users:

| Test | Proves |
|---|---|
| `test_ac_06_1_agent_sees_own_only` | agent B: A's contract and lines not in lists, direct read refused; agent A sees both (AC-06.1) |
| `test_ac_06_2_manager_sees_every_agent` | the manager lists and edits both agents' contracts and lines (AC-06.2) |
| `test_ac_06_4_other_company_hidden` | a company 2 manager sees only company 2's project, unit, plan, contract, lines; company 1 records refused; and the other way round (AC-06.4) |
| `test_agent_and_accountant_reads_all_writes_own` | an agent-accountant reads every contract, edits only their own draft (BR-35) |
| `test_agent_cannot_print_others` | the report refuses agent B (BR-35) |
| `test_access.py` (Story 02), unchanged | AC-06.3 and AC-06.5 still hold with every rule on |

Every test from Stories 02–05 and 08 passed with the rules on, without changes. One test,
`test_ac_09_1_agent_cancels_draft`, still expects `AccessError` for agent B, which now comes
from the record rule. Total: 83 tests.

**Negative checks** (seen failing, then undone before `git add`):

| Check | Change | Result |
|---|---|---|
| N1 | drop the manager rule on contracts | 43 tests error: managers cannot see agents' contracts, so they cannot confirm them, and the test fixtures fail |
| N2 | give the contract's multi-company rule the accountant group | T1 fails: the company 2 manager sees company 1's contract |
| N3 | drop the line agent rule (keep the contract rule) | T3 fails: agent B lists A's 34 lines |

The first try at N2 gave the multi-company rule the **agent** group, and T1 still passed: the
company 2 user is a manager, and the manager has the agent group through `implied_ids`.

## Alternatives considered

- **Make the groups independent** (the manager no longer implies the agent). It would avoid
  the manager rule, but a manager would lose the agent's access rights and menus, and every
  ACL line would need a manager copy. The "see all" rule is one record and the Odoo way.
- **Hide other agents' contracts only in the views** (a default filter "My contracts"). Not
  security: the API, exports and links would still show them.
- **Put `state = 'draft'` in the agent rule's domain for writes.** The contract's `write()`
  and the schedule lock already refuse edits outside draft, with a clear message. A rule
  would give a generic access error instead.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-06--record-rules-agents-see-their-own-contracts-multi-company).

1. What is the difference between an access right (`ir.model.access.csv`) and a record rule
   (`ir.rule`)? Give one thing in this module that each of them decides.
2. Odoo combines global rules and group rules differently. Explain how, and use it to say why
   a manager needs the "see all" rule even though nobody changed the groups.
3. The collections and accounting "read all" rule has `perm_read` only. For a user who is both
   an agent and an accountant, which rules apply when they read agent A's contract, and which
   when they try to edit it? What would go wrong if the rule had all four perms?
