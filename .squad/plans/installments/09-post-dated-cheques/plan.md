# 09 — Post-dated cheques

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/09-post-dated-cheques/intake.md`
- **Branch:** `story/09-post-dated-cheques`
- **Status:** Done Criteria approved 2026-11-25; in progress

---

## Prerequisites

- Stories 01–08 merged; `main` at `d046c3d`; CI green on `main`; `make test` gives 0 failed of 90
  tests with a clean log; `make lint` passes.
- Local `main` clean and in sync with `origin/main`.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Nothing new to install. Tests use `re_test` and free ports
  (`make test ARGS="--http-port 8097 --gevent-port 8098"`).
- **Scope change, decided by the maintainer:** Story 09 was a stretch story ("moves to v1.1 if time
  runs short"). It is now part of v1, before Story 10. Step 0 updates every document that still says
  otherwise. Demo data, the GIF and the release tag stay in Story 10.

## Story Goal

Let a collections officer record the post-dated cheques (شيكات آجلة) a buyer hands over and track
each one ([US-13](../../../../docs/business-requirements.md#us-13--track-post-dated-cheques "US-13: As a collections officer, I want to record the cheques a buyer hands over and track each one, so that I know which to deposit today and which have bounced.")): a cheque is its own record on one schedule line
([BR-40](../../../../docs/business-requirements.md#post-dated-cheques "BR-40: A post-dated cheque is its own record, linked to one schedule line: cheque number, bank, cheque date, amount and status. A line can have several cheques over time, because a bounced cheque is replaced, so the history is kept.")), it moves **held → deposited → cleared** or **bounced** and nothing else
([BR-41](../../../../docs/business-requirements.md#post-dated-cheques "BR-41: Cheque states: held → deposited → cleared or bounced. No other transitions. A bounced cheque can be replaced by a new held cheque on the same line.")), a bounced cheque stays in the history and a new one can be added, and a **To Deposit**
list shows the held cheques dated today or earlier.

Cheque status is **information only** ([BR-42](../../../../docs/business-requirements.md#post-dated-cheques "BR-42: Cheque status is information only. It never changes whether a line is paid, overdue or accruing late fees — BR-24 alone decides that. v1 creates no accounting entries for cheques.")): it never changes a line's payment state,
overdue flag or late fee, and creates no accounting entry. Accounting alone decides those (BR-24).
Rights follow [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.") and the rights matrix: agents read the cheques on their own contracts,
collections officers and managers record them, accountants read them.

Not in this story (intake "Out of scope"): cheque journals, entries on deposit or bounce,
bounced-cheque fees, bank integration.

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/09-post-dated-cheques/intake.md` — US-13, BR-40–BR-42, BR-35,
  AC-13.1–AC-13.5, the rights matrix row "Post-dated cheques: R (own) / W / W / R".
- `docs/business-requirements.md` — §1.2 BR-40–42, §1.3 US-13, §1.4 story map, §4 rights matrix,
  §7 "Post-dated cheque accounting", §8 Q1 (option b: light tracking, no accounting).
- `addons/real_estate_eg/models/real_estate_installment.py` — the line: `contract_id`, `company_id`
  (related, stored, indexed), `currency_id`, `state` (stored compute from the invoice, BR-24),
  `is_overdue`, `days_past_due`, `late_fee_accrued`; `create()` / `write()` locked by
  `_check_schedule_editable()` once the contract is not draft (BR-19). A cheque never writes the
  line, so that lock is not touched.
- `addons/real_estate_eg/models/real_estate_contract.py` — `_inherit = ["mail.thread",
  "mail.activity.mixin"]`, `state` with `tracking=True`, `action_bill_late_fees()` (the pattern for
  "collections or manager" through `has_group(...collections)`, since the manager group implies it).
- `addons/real_estate_eg/security/security.xml` — the three groups; manager implies agent and
  collections.
- `addons/real_estate_eg/security/ir.model.access.csv` — one line per model and role; the accountant
  role is `account.group_account_invoice`.
- `addons/real_estate_eg/security/ir_rules.xml` — Story 06 pattern: a global multi-company rule per
  model; an agent rule through the contract (`contract_id.user_id = user.id`); manager "see all";
  read-only "see all" for collections and accountants.
- `addons/real_estate_eg/views/real_estate_menus.xml` — the **Collections** menu (groups:
  collections, manager, accountant) with Due This Month, Overdue, Overdue Analysis, At-Risk
  Contracts. The To Deposit list goes here.
- `addons/real_estate_eg/views/real_estate_installment_views.xml` — action domains with relative
  dates (`'today =1d'`); read-only collections list.
- `addons/real_estate_eg/views/real_estate_contract_views.xml` — the contract form (`<header>`,
  `<sheet>`, `<chatter />`); it has no button box yet.
- `addons/real_estate_eg/tests/common.py` — `RealEstateCommon`: `agent_a`, `agent_b`, `manager`,
  `collections`, `accountant`, `create_contract()`, `_example_a()`, `_installment_1_invoiced()`,
  `_pay()`, `_night()`.
- `addons/real_estate_eg/tests/test_collections.py` — `_domain(xmlid)` reads an action's domain with
  `literal_eval`; the same check is used for To Deposit.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/addons/mail/models/mail_thread.py` — `mail.thread`; `_message_track()` logs
  changes of fields with `tracking=True` in the chatter (each state change gets a line);
  `mail_create_nosubscribe` context key.
- `odoo-src/odoo/addons/mail/models/models.py` — where the `tracking` field attribute is handled.
- `odoo-src/odoo/odoo/orm/table_objects.py` — `class Constraint` (`models.Constraint("CHECK
  ...")`), as `_amount_positive` on the line.
- `odoo-src/odoo/odoo/orm/models.py` — `_read_group()` for the contract's cheque count (runs under
  the user's record rules).
- `odoo-src/odoo/odoo/tools/date_utils.py` — `parse_date()`: `'today'` alone is a valid relative
  date; `odoo/orm/domains.py` `_optimize_type_date_relative()` applies it for `<=`. So the To Deposit
  domain is `[('state', '=', 'held'), ('date', '<=', 'today')]`, the same on the server and in tests.
- `odoo-src/odoo/odoo/addons/base/models/ir_rule.py` — `_compute_domain()`: group rules OR-ed,
  global rules AND-ed (Story 06).
- `odoo-src/odoo/odoo/addons/base/security/ir.model.access.csv` — `res.bank`: `group_user` may only
  read, creating needs `group_partner_manager`, which collections officers do not have. So the bank
  is a plain text field (see Step 1).
- `odoo-src/odoo/addons/sale/views/sale_order_views.xml` — `<div class="oe_button_box"
  name="button_box">` (smart button pattern); `addons/sale/models/sale_order.py`
  `action_view_invoice()` (a button returning a window action).

## Implementation tasks

Small steps, in order, **one commit per step**, each ending with a Key points block (built + ids,
Odoo concept, trap, one-line takeaway). Files are new unless marked *(edit)*. All under
`addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Branch, plan, and "cheques are v1" in the docs.** `git switch -c
story/09-post-dated-cheques` from up-to-date `main`. Commit this plan, the overview row and the
scope change, editing only what is now untrue:
- `README.md` *(edit)*: roadmap row 09 "Post-dated cheques" (drop "(stretch)"), status "in
  progress"; row 07 → "done".
- `.squad/plans/installments/00-overview.md` *(edit)*: row 09 title and file; the "Story 09 is a
  stretch" note becomes "pulled into v1"; row 10 depends on 01–09.
- `docs/business-requirements.md` *(edit)*: §1.1 "(a stretch story — see §1.4)" removed; §1.2
  heading "Post-dated cheques *(stretch — see §1.4)*" → "Post-dated cheques"; §1.3 US-13 heading
  without "*(stretch)*"; §1.4 row "Story 09 — **stretch** ..." → "Story 09"; §8 Q1 "Its own stretch
  story (Story 09)" → "Its own story (Story 09)". §7 stays (cheque *accounting* is still beyond v1).
  The document has no change log; the header gets a dated line saying Story 09 moved into v1.
- `docs/project-plan.md` *(edit)*: story table row 09 without "*(stretch)*" and without "If time
  runs short, this moves to v1.1".
- Local only (gitignored, not committed): `00-overview.ar.md`, `docs/business-requirements.ar.md`,
  `docs/project-plan.ar.md` get the same changes;
  `docs/private/how-to-learn-this-project.md` and `.ar.md` get the cheque model in the module map
  and Stage 3, and lose the line saying cheques are not in v1.

**Step 1 — The cheque model, rights and rules** (`models/real_estate_cheque.py`,
`models/__init__.py` *(edit)*, `models/real_estate_installment.py` *(edit)*,
`security/ir.model.access.csv` *(edit)*, `security/ir_rules.xml` *(edit)*, `tests/test_cheques.py`,
`tests/__init__.py` *(edit)*). *BR-40, BR-35, AC-13.1.*
1. `real.estate.cheque`, `_inherit = ["mail.thread"]`, `_order = "date, id"`:
   `name` (Char, "Cheque Number", required), `bank_name` (Char, required — plain text, see
   `res.bank` above), `date` (Date, "Cheque Date", required), `amount` (Monetary, required,
   `CHECK (amount > 0)` as a `models.Constraint`), `line_id` (Many2one `real.estate.installment`,
   required, indexed, `ondelete="restrict"`), `contract_id` (related `line_id.contract_id`, stored,
   indexed — for the agent rule, grouping and the contract button), `partner_id` (related, not
   stored), `company_id` (related `line_id.company_id`, stored, indexed), `currency_id` (related),
   `state` (Selection `held`, `deposited`, `cleared`, `bounced`; default `held`; `readonly=True`;
   `tracking=True`).
2. On the line: `cheque_ids` (One2many to `line_id`, read only) — the line's cheque history.
3. `create()` refuses a cheque unless the line's contract is `confirmed` or `delivered` (AC-13.1),
   and always starts it `held`, whatever `state` the values carry.
4. Access rights: agent read; collections read/write/create; manager read/write/create;
   accountant read. **Nobody deletes** (BR-40 keeps the history); a typo on a held cheque is fixed by
   editing it (Step 2 allows that only while held).
5. Record rules: global multi-company rule on `company_id`; agent rule
   `[('contract_id.user_id', '=', user.id)]` (agents' read: "R (own)"); collections rule `(1, '=',
   1)` with all permissions (the manager group implies collections); accountant rule `(1, '=', 1)`,
   read only.
6. Tests T1, T2, T8 first. *Check:* `make test`.

**Step 2 — State transitions, enforced in Python** (`models/real_estate_cheque.py` *(edit)*,
`tests/test_cheques.py` *(edit)*). *BR-41, AC-13.2, AC-13.3.*
1. One table of allowed moves: `held → deposited`, `deposited → cleared`, `deposited → bounced`.
2. `write()` checks every `state` change against that table, for every user **including the
   superuser**, and raises `UserError` otherwise. So the rule holds for RPC, imports and code, not
   only for buttons.
3. `write()` refuses changes to number, bank, date, amount or line once a cheque is not `held`.
4. Buttons `action_deposit()`, `action_clear()`, `action_bounce()` only call `write()`; the form
   shows each one in the right state only (UI convenience, not the guard).
5. Replacement (AC-13.3) needs no code: a bounced cheque is final, and a new held cheque on the same
   line is a normal create. The line's `cheque_ids` shows both.
6. Tests T3, T4, T5. *Check:* `make test`.

**Step 3 — Status only: prove BR-42** (`tests/test_cheques.py` *(edit)*). *BR-42, AC-13.4.*
1. No production code: nothing on the line or the contract depends on cheques (no `@api.depends` on
   `cheque_ids`, no cheque step in the nightly job). This step proves it.
2. Test T6. *Check:* `make test`.

**Step 4 — Screens: cheques, To Deposit, contract button** (`views/real_estate_cheque_views.xml`,
`views/real_estate_menus.xml` *(edit)*, `views/real_estate_contract_views.xml` *(edit)*,
`models/real_estate_contract.py` *(edit)*, `__manifest__.py` *(edit)*, `tests/test_cheques.py`
*(edit)*). *AC-13.5, US-13.*
1. Cheque list, form (header with the three buttons and a status bar, chatter) and search view
   (filters Held, Deposited, Bounced; group by status, contract, bank).
2. Two actions: **Cheques** (all) and **To Deposit** with the domain `[('state', '=', 'held'),
   ('date', '<=', 'today')]`, oldest first. Both under the Collections menu.
3. Contract form: a smart button "Cheques" with `cheque_count` (via `_read_group`, under the user's
   rules) and `action_view_cheques()`; this is how agents see the cheques on their own contracts
   (they have no Collections menu).
4. The line picker in the cheque form only offers lines of confirmed or delivered contracts (a
   domain; `create()` from Step 1 is the real guard).
5. Test T7. *Check:* `make test`.

**Step 5 — Whole flow + CI stack.** On `re_dev`: `-u real_estate_eg`; record a cheque, deposit,
bounce, add a replacement, clear it, as the collections user; open the contract as its agent (M1);
log clean. Then `make lint`, `make test-ci`.

**Step 6 — Docs + PR.** `docs/design-notes/09-post-dated-cheques.md` (cheque as its own model, the
state machine in `write()`, why status is information only, record rules, negative checks; 3
explain-back questions); `docs/learning-log.md` *(edit)*; `README.md` *(edit)*: roadmap 09 → in
review. Done Criteria ticked in `plan.md` and `plan.ar.md`. PR; CI green; the maintainer answers the
explain-back questions in `docs/learning-log.md` and merges with "Create a merge commit".

## Edge Cases & Failure Modes

1. **Draft or cancelled contract**: no cheque can be recorded (AC-13.1). A cheque already on a
   contract that is later cancelled stays, and can still move deposited → cleared or bounced (the
   paper cheque is real); no new cheque on it.
2. **Closed contract**: not confirmed or delivered, so no new cheque (all lines are paid anyway).
3. **Skipped steps**: held → cleared and held → bounced are refused — a cheque the bank has not
   seen cannot clear or bounce. Backwards moves (cleared → held, bounced → deposited) are refused.
   Bounced and cleared are final.
4. **Direct writes**: `write({'state': ...})` by RPC, import or `sudo()` goes through the same
   check; the state field is read-only in the form too.
5. **Several cheques on one line**: allowed (BR-40). No sum check against the line amount: a line
   may be covered by two cheques, and status is information only.
6. **Cheque on a paid or overdue line**: allowed; the line stays as accounting says (BR-42).
7. **Cleared ≠ paid**: a cleared cheque does not mark the line paid; the accountant registers the
   payment in accounting, which pays the line (BR-24). The design note says so for users.
8. **Bounced cheque**: stays in the history; the line stays overdue if it is, and keeps accruing
   late fees.
9. **No delete**: no ACL grants unlink; a held cheque with a typo is edited instead.
10. **Schedule lock**: lines of confirmed contracts are locked (BR-19). A cheque never writes its
    line, so recording one does not trip the lock; `cheque_ids` is a One2many, which writes the
    cheque, not the line.
11. **"Today"** is the user's date (`parse_date` starts from the user's timezone), so a cheque dated
    today is in To Deposit from local midnight.
12. **Record rules**: an agent who opens a cheque by URL sees only cheques on their own contracts;
    the contract button count is computed under the same rules.

## Test Plan

Tests in `addons/real_estate_eg/tests/test_cheques.py`, `@tagged("post_install", "-at_install")`,
on `RealEstateCommon`. Every check runs `with_user()` as an agent, manager, collections officer or
accountant — never as admin (except the explicit `sudo()` write in T4) — and nothing relies on demo
data. Dates are fixed with `freeze_time`.

| # | Test | Proves |
|---|---|---|
| T1 | `test_ac_13_1_record_cheque` — on a confirmed contract (and on a delivered one), collections and the manager each record a cheque (number, bank, date, amount) on a line; it is `held`, even when `state: 'cleared'` is passed in the values | AC-13.1, BR-40 |
| T2 | `test_ac_13_1_refused_unless_confirmed` — on a draft contract and on a cancelled one, recording a cheque raises `UserError`; amount 0 is refused | AC-13.1 |
| T3 | `test_ac_13_2_allowed_moves` — held → deposited → cleared on one cheque; held → deposited → bounced on another; each change is logged in the chatter | AC-13.2, BR-41 |
| T4 | `test_ac_13_2_other_moves_refused` — held → cleared, held → bounced, cleared → held, bounced → deposited, cleared → bounced each raise `UserError`, by button and by `write()`, as the manager and as `sudo()`; changing the amount of a deposited cheque is refused | AC-13.2, BR-41 |
| T5 | `test_ac_13_3_bounced_replaced` — a cheque bounces; a new held cheque on the same line is recorded; the line's `cheque_ids` holds both, the bounced one unchanged; collections and the manager cannot delete a cheque | AC-13.3, BR-40 |
| T6 | `test_ac_13_4_status_only` — on an invoiced line past its grace: record, deposit and clear a cheque, then run the nightly job; the line's state, outstanding amount, `is_overdue`, `days_past_due` and `late_fee_accrued` equal those of the same line with no cheque, and no new `account.move` exists. Same with a bounced cheque. Then a real payment in accounting pays the line | AC-13.4, BR-42 |
| T7 | `test_ac_13_5_to_deposit` — under `freeze_time`: held cheques dated yesterday and today are in the To Deposit action's domain; a held cheque dated tomorrow, a deposited one and a bounced one are not | AC-13.5 |
| T8 | `test_cheque_rights` — agent A reads the cheques on their own contract, agent B does not see them; agents and the accountant cannot create or change a cheque (`AccessError`); the accountant reads all; the contract's cheque count follows the same rules | BR-35, rights matrix |
| M1 | *(manual, Step 5)* the To Deposit menu, the cheque form buttons and the contract's Cheques button in the browser, as collections and as the agent | US-13 |
| T9 | `make test` (all 90 earlier tests still pass), `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: allow `held → cleared` in the transition table → T4 fails.
- N2: let `_compute_payment()` mark a line paid when it has a cleared cheque (add `cheque_ids.state`
  to its depends) → T6 fails.
- N3: remove the contract-state check in `create()` → T2 fails.
- N4: give the agent rule `(1, '=', 1)` → T8 fails.

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/09-post-dated-cheques
make test ARGS="--http-port 8097 --gevent-port 8098"   # T1–T8 + the 90 earlier tests, log clean
make lint                                              # pre-commit green
make test-ci                                           # same tests in the CI Docker stack
make run ARGS="-u real_estate_eg --http-port 8097 --gevent-port 8098"   # Step 5 on re_dev; log clean
gh pr checks                                           # pre-commit + test green on the PR
gh run list --branch main --limit 1                    # green after merge
```

## Done Criteria

- [ ] **AC-13.1** Given a confirmed or delivered contract, the officer records a cheque (number,
  bank, date, amount) against a schedule line; it starts **held**. *Proof:* T1, T2.
- [ ] **AC-13.2** A cheque moves held → deposited → cleared or bounced; any other change is refused.
  *Proof:* T3, T4.
- [ ] **AC-13.3** When a cheque bounces, a new cheque can be recorded on the same line; the bounced
  one stays in the line's history. *Proof:* T5.
- [ ] **AC-13.4** Marking a cheque cleared does not change the line's payment status; only a payment
  in accounting does. *Proof:* T6.
- [ ] **AC-13.5** A "To deposit" list shows held cheques dated today or earlier. *Proof:* T7.
