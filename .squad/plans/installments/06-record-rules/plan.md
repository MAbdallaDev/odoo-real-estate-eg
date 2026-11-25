# 06 — Record rules: agents see their own contracts; multi-company

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/06-record-rules/intake.md`
- **Branch:** `story/06-record-rules`
- **Status:** Done Criteria approved 2026-11-25; in progress

---

## Prerequisites

- Stories 01–05 and 08 merged; `main` at `c99a70c`; CI green on `main`; `make test` gives 0 failed
  of 78 tests with a clean log; `make lint` passes.
- Local `main` clean and in sync with `origin/main`.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Nothing new to install. Tests use `re_test` and free ports
  (`make test ARGS="--http-port 8097 --gevent-port 8098"`).

## Story Goal

Story 02 gave each role its **access rights** (which tables it may read or write). This story adds
**record rules** (which rows): a sales agent sees only contracts where they are the agent, and those
contracts' schedule lines; a sales manager, a collections officer and an accountant see all of them
([BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.")). Every model of the module also gets the standard multi-company rule, so a user sees only
the data of the companies they are allowed in ([BR-36](../../../../docs/business-requirements.md#visibility "BR-36: Users only see data of the companies they are allowed in.")).

**The maintainer writes the agent record rule and its test personally** (Step 3, test first). Claude
writes everything else.

Not in this story: portal access for customers (Chapter 7); any change to the rights matrix (decided
in Story 02); cheque rules (Story 09).

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/06-record-rules/intake.md` — the ACs and the rights matrix.
- `docs/business-requirements.md` — [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."), [BR-36](../../../../docs/business-requirements.md#visibility "BR-36: Users only see data of the companies they are allowed in."), [US-06](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "US-06: Agents see only their own contracts"), §4 Actors and roles (rights
  matrix).
- `addons/real_estate_eg/security/security.xml` — the three groups; the manager group **implies** the
  agent and collections groups. The accountant is Odoo's `account.group_account_invoice`.
- `addons/real_estate_eg/security/ir.model.access.csv` — access rights per model and group.
- `addons/real_estate_eg/models/real_estate_contract.py` — `user_id` (the sales agent),
  `company_id` (related to the unit, stored), `write()` (agents edit drafts only),
  `_check_unit_free()` (already `sudo()` for Story 06), `action_cancel()` (draft: own agent or
  manager), every other `sudo()`.
- `addons/real_estate_eg/models/real_estate_installment.py` — `contract_id`, `company_id` (related,
  stored), `_check_schedule_editable()`, every `sudo()`.
- `addons/real_estate_eg/models/real_estate_unit.py`, `real_estate_project.py`,
  `real_estate_plan_template.py` — each has a stored `company_id`.
- `addons/real_estate_eg/models/res_partner.py` — `_compute_same_vat_partner_id`-style `sudo()`.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon`: `agent_a`, `agent_b`, `manager`,
  `collections`, `accountant`, `create_contract()`, `add_schedule()`.
- `addons/real_estate_eg/tests/test_access.py` — AC-06.3 / AC-06.5 from Story 02, re-run here with
  the rules on.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/odoo/addons/base/models/ir_rule.py` — `ir.rule` fields `model_id`, `groups`
  (Many2many), `domain_force`, `perm_read` / `perm_write` / `perm_create` / `perm_unlink` (all
  default True). `_eval_context()` gives the domain `user` and `company_ids` (the active
  companies). `_compute_domain()`: rules **without** groups are *global* and are AND-ed; rules
  **with** groups apply only to members, and those are OR-ed together, then AND-ed with the global
  ones.
- `odoo-src/odoo/addons/sale/security/ir_rules.xml` — the patterns to copy:
  `sale_order_comp_rule` (multi-company, domain `[('company_id', 'in', company_ids)]`, no groups),
  `sale_order_personal_rule` (own orders for `group_sale_salesman`, `user_id` compared with
  `user.id`) and `sale_order_see_all` (`[(1, '=', 1)]` for `group_sale_salesman_all_leads`);
  `sale_order_line_rule_portal` shows a rule on lines through the parent (`order_id.…`).
- `odoo-src/odoo/odoo/orm/fields.py` — stored computed fields default to `compute_sudo = True`, so
  the unit state and the contract's at-risk flag are recomputed whatever the user may see.
- `odoo-src/odoo/odoo/orm/models.py` — `check_access(operation)`.
- `odoo-src/odoo/addons/account/tests/common.py` — `setup_other_company()` /
  `_create_company()` (a second company with its own chart; the base helper in
  `odoo-src/odoo/odoo/addons/base/tests/common.py` links it to the setup user).
- `odoo-src/odoo/odoo/tests/common.py` — `new_test_user(env, login, groups, **kwargs)`: extra
  kwargs (`company_id`, `company_ids`) go to the user's `create()`.

## Implementation tasks

Small steps, in order, **one commit per step**, each ending with a Key points block (built + ids,
Odoo concept, trap, one-line takeaway). Files are new unless marked *(edit)*. All under
`addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Branch and plan commit.** `git switch -c story/06-record-rules` from up-to-date `main`;
commit this plan and the overview row.

**Step 1 — Multi-company rules** (`security/ir_rules.xml`, `__manifest__.py` *(edit)*,
`tests/test_record_rules.py`, `tests/__init__.py` *(edit)*). *[BR-36](../../../../docs/business-requirements.md#visibility "BR-36: Users only see data of the companies they are allowed in."), [AC-06.4](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.4: A user allowed only in company 2 cannot see company 1's contracts or units.").*
1. One global rule (no groups) per model, domain copied from `sale_order_comp_rule`:
   `[('company_id', 'in', company_ids)]` on `real.estate.project`, `real.estate.unit`,
   `real.estate.plan.template`, `real.estate.contract`, `real.estate.installment`. Every
   `company_id` is required or related and stored, so no `('company_id', '=', False)` branch.
2. `security/ir_rules.xml` loads after `ir.model.access.csv` in the manifest.
3. The two wizards (`real.estate.contract.cancel`, `real.estate.schedule.generate`) are transient
   and store no company of their own: no rule.
4. T1. *Check:* `make test`.

**Step 2 — "See all" rules for managers, collections and accountants** (`security/ir_rules.xml`
*(edit)*, `tests/test_record_rules.py` *(edit)*). *[BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."), [AC-06.2](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.2: A manager sees contracts of every agent.").*
1. The manager group implies the agent group, so once an agent rule exists it applies to managers
   too. Group rules are OR-ed, so a manager rule with `[(1, '=', 1)]` (all four perms) on contracts
   and lines gives them everything back, as `sale_order_see_all` does.
2. Collections officers and accountants: a read-only "see all" rule (`perm_read` only) on contracts
   and lines, groups `group_real_estate_collections` and `account.group_account_invoice`. Read only
   on purpose: a user who is both an agent and an accountant still writes only their own drafts.
3. T2 (passes before Step 3 too; it guards the manager after it). *Check:* `make test`.

**Step 3 — MAINTAINER TASK: the agent record rule, test first** (`tests/test_record_rules.py`
*(edit)*, `security/ir_rules.xml` *(edit)*). *[BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."), [AC-06.1](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.1: Given agent A owns contract X, when agent B opens the contracts list, X is not there, and opening X directly gives an access error.").*
1. **Test first** (T3): agent A owns contract X (with a schedule). As agent B: X is not in
   `search([])` of contracts, its lines are not in `search([])` of lines, and reading X or one of
   its lines directly raises `AccessError`. As agent A: X and its lines are visible. Run it: it must
   **fail** before the rule exists.
2. **Then the rules**: one on `real.estate.contract` and one on `real.estate.installment`, for
   `group_real_estate_agent`, comparing the agent field with the current user (the line reaches it
   through its contract). Run T3 again: green.
3. Claude gives a short teaching brief before this step, reviews the code after, and does not write
   it. *Check:* the maintainer runs `make test`.

**Step 4 — Existing tests with the rules on** (`tests/*` *(edit)* only if needed). *[BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.").*
1. Full `make test`. Any test that relied on an agent seeing another agent's contract is fixed
   honestly: the action runs as the right user, or the test now expects `AccessError`. No rule is
   loosened to make a test pass.
2. Known case: `test_ac_09_1_agent_cancels_draft` — agent B cancelling A's draft still raises
   `AccessError`, now from the record rule (reading the contract) before the Python check. Kept; the
   docstring says so.
3. `test_access.py`: docstring updated (rules are on now); AC-06.3 and AC-06.5 run unchanged with the
   rules active ([AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule."), [AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.")). *Check:* `make test`.

**Step 5 — `sudo()` audit** (`models/*.py` *(edit)*, `report/*.py` *(edit)* if needed).
1. Every `sudo()` from Stories 02–05 is read again with the rules on. Each keeps a one-line comment
   saying why (locked schedule, accounting records the user has no rights on, a unit taken by an
   agent the user cannot see). None is added to hide a rule from a user who should not see the data.
2. The contract report reads `browse(docids)` as the user: an agent cannot print another agent's
   contract (covered in T3's spirit by an extra assertion in T5). *Check:* `make test`.

**Step 6 — Whole flow + CI stack.** On `re_dev`: `-u real_estate_eg`; two agents, a manager, a
collections user and a second company (inside a rolled-back `make shell` transaction or by hand);
check the lists. Log clean. Then `make lint`, `make test-ci`.

**Step 7 — Docs + PR.** `docs/design-notes/06-record-rules.md` (access rights vs record rules, global
vs group rules and how they combine, why managers need a "see all" rule, read-only "see all" for
collections and accountants, `compute_sudo` on stored computes, the `sudo()` audit, negative checks;
3 explain-back questions); `docs/learning-log.md`; `README.md` *(edit)*: roadmap 05 → done, 06 → in
review. Done Criteria ticked in `plan.md` and `plan.ar.md`. PR; CI green; the maintainer answers
the explain-back questions in `docs/learning-log.md` and merges with "Create a merge commit".

## Edge Cases & Failure Modes

1. **Manager implies agent** ([BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.")): without the "see all" rule, the agent rule would hide other
   agents' contracts from managers. Group rules are OR-ed, so the manager rule restores them.
2. **Global vs group**: the multi-company rules have no groups, so they are AND-ed with everything —
   a manager allowed only in company 2 still sees nothing of company 1 ([AC-06.4](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.4: A user allowed only in company 2 cannot see company 1's contracts or units.")).
3. **Agent + accountant on one user**: the accountant rule is read-only, so writes still follow the
   agent rule (own drafts only).
4. **Lines follow their contract**: a schedule line has no agent of its own; its rule goes through
   `contract_id`, so a new agent on the contract moves the lines with it.
5. **Unit already sold by another agent** ([BR-04](../../../../docs/business-requirements.md#projects-and-units "BR-04: A unit can have at most one contract that is not cancelled. Creating a second one fails, whoever tries and in whatever order (the double-sale case). It is enforced in the database, so it holds even when two users save at the same moment.")): `_check_unit_free()` searches as superuser,
   so agent B still gets the "unit already has contract …" message (reference only, no customer).
6. **Stored computes** (unit state, at-risk) are recomputed as superuser (`compute_sudo`), so a
   change by one agent updates fields other users read. Non-stored computes run as the user and
   only see that user's rows.
7. **Nightly job** runs as superuser: rules do not apply to it.
8. **Transient wizards** are already limited to their creator by Odoo; the contract they point to is
   still checked when they run.
9. **Late-fee invoices and schedule-line invoices** are `account.move` records: Odoo's own
   accounting rules and groups cover them; nothing new here.
10. **Active companies**: `company_ids` is the set of companies active in the switcher, not every
    allowed one; tests set the user's companies explicitly.

## Test Plan

Tests under `addons/real_estate_eg/tests/test_record_rules.py`, `@tagged("post_install",
"-at_install")`, on `RealEstateCommon`. Every check runs `with_user()` as an agent, manager,
collections officer, accountant or company-2 user — never as admin — and nothing relies on demo data.

| # | Test | Proves |
|---|---|---|
| T1 | `test_ac_06_4_other_company_hidden` — a second company with its own project, unit and contract; a manager allowed only in company 2 sees its unit and contract, not company 1's; reading a company 1 contract or unit raises `AccessError`; same for projects, plans and lines | [AC-06.4](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.4: A user allowed only in company 2 cannot see company 1's contracts or units."), [BR-36](../../../../docs/business-requirements.md#visibility "BR-36: Users only see data of the companies they are allowed in.") |
| T2 | `test_ac_06_2_manager_sees_every_agent` — contracts of agent A and agent B both in the manager's `search([])`, with their lines; the manager can edit both drafts | [AC-06.2](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.2: A manager sees contracts of every agent.") |
| T3 | **maintainer** `test_ac_06_1_agent_sees_own_only` — see Step 3 | [AC-06.1](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.1: Given agent A owns contract X, when agent B opens the contracts list, X is not there, and opening X directly gives an access error.") |
| T4 | `test_access.py` — AC-06.3 and AC-06.5, unchanged, with the rules on (collections and accountant see every agent's contracts and lines, edit none) | [AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule."), [AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.") |
| T5 | `test_agent_cannot_print_others` — agent B rendering agent A's contract report raises `AccessError`; agent A can | [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.") |
| T6 | `make test` (all earlier tests still pass), `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: drop the manager "see all" rule → T2 fails (manager sees only own contracts).
- N2: give the contract's multi-company rule a group the company 2 user is not in (the
  accountant group) → T1 fails (company 1 visible). With the agent group it would still pass:
  the manager has that group through `implied_ids`.
- N3: drop the line rule (keep the contract rule) → T3 fails (agent B lists A's lines).

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/06-record-rules
make test ARGS="--http-port 8097 --gevent-port 8098"   # T1–T5 + the 78 earlier tests, log clean
make lint                                              # pre-commit green
make test-ci                                           # same tests in the CI Docker stack
make run ARGS="-u real_estate_eg --http-port 8097 --gevent-port 8098"   # Step 6 on re_dev; log clean
gh pr checks                                           # pre-commit + test green on the PR
gh run list --branch main --limit 1                    # green after merge
```

## Done Criteria

- [ ] **[AC-06.1](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.1: Given agent A owns contract X, when agent B opens the contracts list, X is not there, and opening X directly gives an access error.")** Agent A owns contract X: agent B does not see X (or its lines) in the list, and
  opening X directly gives an access error. *Proof:* T3 (maintainer).
- [ ] **[AC-06.2](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.2: A manager sees contracts of every agent.")** A manager sees the contracts of every agent. *Proof:* T2.
- [ ] **[AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule.")** A collections officer sees all contracts but cannot edit price, plan or
  schedule — with the rules on. *Proof:* T4.
- [ ] **[AC-06.4](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.4: A user allowed only in company 2 cannot see company 1's contracts or units.")** A user allowed only in company 2 cannot see company 1's contracts or units.
  *Proof:* T1.
- [ ] **[AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.")** An accountant sees all contracts and schedules but cannot edit them — with the
  rules on. *Proof:* T4.
