# 02 — Core models, views, states and access rights

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/02-core-models/intake.md`
- **Branch:** `story/02-core-models`
- **Status:** awaiting maintainer approval of the Done Criteria

---

## Prerequisites

- Story 01 merged (PR #1, merge commit `14368e4`); CI green on `main`.
- Local `main` clean and in sync with `origin/main`.
- `make test`, `make lint` and `make test-ci` green on `main` before the branch is cut.
- Odoo source at `odoo-src/odoo`, commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` (every Odoo
  symbol below was read at this commit).
- Nothing new to install: `freezegun` (used by one test) is already in Odoo's `requirements.txt`.

## Story Goal

A sales agent can create a contract for an available unit and a customer; the unit shows
**reserved**, the contract gets a sequence reference and a price frozen from the unit. A sales
manager confirms it (unit **sold**), records delivery (unit **delivered**) or cancels it with a
written reason (unit **available** again). A unit can never carry two live contracts, even when two
users save at the same moment. Everyone works through real security groups — agent, manager,
collections officer, and Odoo's own Invoicing group for accountants — so every test from here on
runs as a non-admin user.

Not in this story: payment plans and the schedule (Story 03), so confirmation checks identity only;
invoices, retention, refunds and closing (Story 04); record rules, so agents still see each other's
contracts until Story 06.

## Context — Read These Files First

**In the repo:**

- `.squad/stories/installments/02-core-models/intake.md` — the ACs below, the rights matrix, the
  state diagrams, fixtures (§6.1, §6.2).
- `docs/business-requirements.md` — [BR-01](../../../../docs/business-requirements.md#projects-and-units "BR-01: A unit belongs to exactly one project. A unit's code is unique within its company.")…[BR-13](../../../../docs/business-requirements.md#contracts "BR-13: A contract that is not draft cannot be deleted."), [BR-32](../../../../docs/business-requirements.md#cancellation "BR-32: A draft contract can be cancelled by its agent with no consequences. A confirmed contract can be cancelled only by a manager, with a written reason. A delivered or closed contract cannot be cancelled in v1."), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."); §4 *Actors and roles*; §6.6
  example A (unit `HNC-B07-0302`, 165 m², 8,580,000).
- `docs/design-notes/01-environment.md` — how tests are selected and run, the log check.
- `addons/real_estate_eg/__manifest__.py`, `tests/test_smoke.py` — the skeleton this story extends.

**Odoo 19 source (read at the commit above):**

- `odoo-src/odoo/addons/sale/models/sale_order.py` — the shape the contract copies:
  - `SALE_ORDER_STATE` list + `state = fields.Selection(..., readonly=True, copy=False, index=True,
    tracking=3, default='draft')`;
  - `name` defaulting to `_('New')`, replaced in `create()` (`@api.model_create_multi`) by
    `self.env['ir.sequence'].with_company(...).next_by_code('sale.order', sequence_date=...)`;
  - `_check_company_auto = True`, `company_id` default `self.env.company`, `check_company=True` on
    relations;
  - `@api.ondelete(at_uninstall=False)` on `_unlink_except_draft_or_cancel` raising `UserError`;
  - public `action_confirm()` that checks each record (`_confirmation_error_message()`), then writes
    the new state; `action_cancel()` delegating to `_action_cancel()`;
  - stored computed fields with `store=True, readonly=False, precompute=True` (pricelist, currency).
- `odoo-src/odoo/addons/sale/data/ir_sequence_data.xml` — `ir.sequence` record (`code`, `prefix`,
  `padding`, `company_id` `False`) inside `<odoo noupdate="1">`.
- `odoo-src/odoo/addons/sale/views/sale_order_views.xml` — `<list>` (not `<tree>`), statusbar
  `widget="statusbar"`, buttons with `invisible="state != 'draft'"`, `<chatter/>` in the form.
- `odoo-src/odoo/odoo/orm/table_objects.py` — `models.Constraint(definition, message)` and
  `models.UniqueIndex(definition, message)`; a `UniqueIndex` definition may carry a `WHERE` clause
  (used in core, e.g. `addons/product/models/product_product.py`:
  `models.UniqueIndex("(product_tmpl_id, combination_indices) WHERE active IS TRUE")`).
- `odoo-src/odoo/odoo/orm/models.py` — `_sql_error_to_message()`: a violated constraint or unique
  index is reported with its declared message.
- `odoo-src/odoo/odoo/service/model.py` — on an `IntegrityError` the request is rolled back and a
  `ValidationError("The operation cannot be completed: …")` is shown, so the race case gets a clean
  message in the UI.
- `odoo-src/odoo/odoo/orm/fields.py` — `compute_sudo` defaults to `store` for computed fields, so a
  stored computed unit status is recomputed as superuser (it stays right once Story 06's record
  rules hide other agents' contracts).
- `odoo-src/odoo/odoo/addons/base/models/ir_sequence.py` — `next_by_code()` checks `read` access on
  `ir.sequence`, which `base.group_user` has (`base/security/ir.model.access.csv`).
- `odoo-src/odoo/odoo/addons/base/models/res_groups_privilege.py` and
  `odoo-src/odoo/addons/sales_team/security/sales_team_security.xml` — Odoo 19 groups: a
  `res.groups.privilege` (with `category_id`) groups the `res.groups` records (`privilege_id`,
  `sequence`, `implied_ids`, `user_ids`). The manifest category `Real Estate` already created
  `base.module_category_real_estate` (`odoo/modules/db.py`, `create_categories`).
- `odoo-src/odoo/addons/account/security/account_security.xml` — with Community `account` alone,
  only `account.group_account_invoice` ("Invoicing") and `account.group_account_manager` are meant to
  be used; the manager group implies the invoicing one. Accountants get read access through
  `account.group_account_invoice`.
- `odoo-src/odoo/odoo/addons/base/models/res_partner.py` — `is_company` (Boolean) and
  `company_type`; no core field named `nationality`, `national_id` or `passport_number`.
- `odoo-src/odoo/odoo/addons/base/views/res_partner_views.xml` — form `base.view_partner_form`,
  `<field name="vat">` as the anchor for the identity fields.
- `odoo-src/odoo/odoo/addons/base/security/ir.model.access.csv` — `res.partner` is read-only for
  `base.group_user`; create/write needs `base.group_partner_manager`.
- `odoo-src/odoo/odoo/tests/common.py` — `new_test_user(env, login, groups=...)`; `assertRaises`
  wraps the block in a savepoint (and clears the cache for `AccessError`).
- `odoo-src/odoo/odoo/tests/form.py` — `Form`, to drive the cancel wizard like the UI does.
- `odoo-src/odoo/odoo/tools/misc.py` — `mute_logger`; `odoo-src/odoo/odoo/sql_db.py` logs a failed
  query as `ERROR` on logger `odoo.sql_db`. Muting it keeps the expected error of the database-index
  test out of the log (the log check fails on `ERROR`).
- `odoo-src/odoo/addons/sale/tests/test_access_rights.py` — how core tests access rights per group.

## Implementation tasks

Small review steps, in order. Each step: what and why with its US / BR / AC → the code, each block
commented with the rule it implements → what it links to (Odoo core file, earlier steps) → the
maintainer runs the check → review → **one commit per step**. Tests are written in the same step as
the code they prove. A step that turns out too big is split, not rushed.

Files are new unless marked *(edit)*. All under `addons/real_estate_eg/` unless a path says otherwise.

**Step 0 — Teaching brief, branch, plan commit.** Models and fields, stored computed fields, states
and buttons, groups / ACLs vs record rules. `git switch -c story/02-core-models` from up-to-date
`main`; commit this plan and the overview row.

**Step 1 — Security groups** (`security/security.xml`; `__manifest__.py` *(edit)*). *[US-06](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "US-06: Agents see only their own contracts"), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.").*
1. `res.groups.privilege` "Real Estate", `category_id` `base.module_category_real_estate`.
2. `group_real_estate_agent` (implies `base.group_user` and `base.group_partner_manager`, so agents
   can create customers), `group_real_estate_collections` (implies `base.group_user`),
   `group_real_estate_manager` (implies agent and collections; `user_ids` adds `base.user_root` and
   `base.user_admin`, as `sales_team` does).
3. Accountants: no new group; `account.group_account_invoice` gets read rights in Steps 2, 3, 5.
*Check:* `make test`; the "Real Estate" picker shows in a user form on `re_dev`.

**Step 2 — Projects** (`models/__init__.py`, `models/real_estate_project.py`,
`security/ir.model.access.csv`, `views/real_estate_project_views.xml`, `views/real_estate_menus.xml`;
`__init__.py`, `__manifest__.py` *(edit)*). *[BR-01](../../../../docs/business-requirements.md#projects-and-units "BR-01: A unit belongs to exactly one project. A unit's code is unique within its company.") (company), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.") rights matrix.*
1. `real.estate.project` — `name`, `code`, `location`, `expected_delivery_date`, `company_id`,
   `currency_id` (related to the company), `active`. `models.Constraint` "UNIQUE (company_id, code)".
2. ACL rows: agent R, collections R, manager RWCD, `account.group_account_invoice` R.
3. List, form, search views; root menu "Real Estate" → Projects (each action defined before its menu).
*Check:* `make test`; create a project in the browser.

**Step 3 — Units** (`models/real_estate_unit.py`, ACL rows, `views/real_estate_unit_views.xml`,
menus *(edit)*). *[BR-01](../../../../docs/business-requirements.md#projects-and-units "BR-01: A unit belongs to exactly one project. A unit's code is unique within its company."), [BR-02](../../../../docs/business-requirements.md#projects-and-units "BR-02: A unit has a type, area (m²), floor and list price (EGP). Price per m² is shown, computed from list price ÷ area.").*
1. `real.estate.unit` — `code` (rec name), `project_id` (required, `ondelete='restrict'`,
   `check_company=True`), `unit_type` (Selection: apartment, duplex, chalet, twin house, office,
   retail), `bedrooms`, `area` (m²), `floor`, `list_price` (Monetary), `price_per_sqm` (Monetary,
   computed = list price ÷ area), `company_id`, `currency_id`. Project gets `unit_ids`, `unit_count`.
2. [BR-01](../../../../docs/business-requirements.md#projects-and-units "BR-01: A unit belongs to exactly one project. A unit's code is unique within its company."): `models.Constraint` "UNIQUE (company_id, code)"; CHECK `area > 0`, `list_price >= 0`.
3. ACL rows as projects; list, form, search views; menu Units.
*Check:* `make test`; create unit `HNC-B07-0302` (165 m², 8,580,000) → price per m² 52,000.

**Step 4 — Customer identity** (`models/res_partner.py`, `views/res_partner_views.xml`,
`tests/__init__.py` *(edit)*, `tests/test_partner.py`). *[BR-05](../../../../docs/business-requirements.md#customers "BR-05: The customer is a contact (person or company). Each individual buyer has a nationality: Egyptian or foreign (a field on the contact — the address country does not say it). An Egyptian individual must have a national ID (الرقم القومي) before the contract can be confirmed; a foreign individual must have a passport number instead. A company buyer has no identity check in v1."), [BR-06](../../../../docs/business-requirements.md#customers "BR-06: A national ID is valid only if it has 14 digits, its first digit is 2 (born 1900–1999) or 3 (born 2000–2099), and digits 2–7 form a real date of birth (YYMMDD) that is not in the future."), [AC-01.4](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.4: Given a customer's national ID is 29901158800017 (born 15 Jan 1999), the system accepts it; given 19901158800017 (first digit 1), 29902308800017 (30 February) or 33001018800017 (born 1 Jan 2030, in the future), the system refuses it.").*
1. Inherit `res.partner`: `nationality` (Selection egyptian / foreign), `national_id`,
   `passport_number`.
2. [BR-06](../../../../docs/business-requirements.md#customers "BR-06: A national ID is valid only if it has 14 digits, its first digit is 2 (born 1900–1999) or 3 (born 2000–2099), and digits 2–7 form a real date of birth (YYMMDD) that is not in the future.") in `@api.constrains('national_id')`: 14 digits; first digit 2 (19xx) or 3 (20xx); digits
   2–7 a real date (`datetime.date` construction fails on 30 February); not after today.
3. Form view inheriting `base.view_partner_form`, after `vat`; hidden for companies
   (`invisible="is_company"`).
4. T5 (with today frozen by `freezegun`).
*Check:* `make test` (T5 green); try a wrong ID in the browser.

**Step 5 — Contract basics** (`models/real_estate_contract.py`, `data/ir_sequence_data.xml`, ACL
rows, `views/real_estate_contract_views.xml`, menus *(edit)*, `tests/common.py`,
`tests/test_contract.py`). *[US-01](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "US-01: Create a contract for an available unit"), [BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date."), [BR-08](../../../../docs/business-requirements.md#contracts "BR-08: The contract price is frozen at the unit's list price when the contract is created. Changing the unit's list price afterwards does not change existing contracts. If the unit is changed on a draft contract, the price is taken again from the new unit."), [AC-01.1](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.1: Given unit HNC-B07-0302 is available, when an agent creates a contract for it, then the contract is draft, gets a reference from the sequence, its price is 8,580,000 EGP, and the unit shows reserved."), [AC-01.2](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.2: Given the unit's list price is then changed to 9,000,000, when the agent reopens the contract, then its price is still 8,580,000."), [AC-01.6](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.6: Given a draft contract for HNC-B07-0302 at 8,580,000, when the agent changes the unit to a 2-bedroom HNC unit, then the price becomes 6,500,000.").*
1. `real.estate.contract`, `_inherit = ['mail.thread', 'mail.activity.mixin']`,
   `_check_company_auto = True`, `_order = 'id desc'`.
2. Fields: `name` (reference, default `New`, readonly, `copy=False`), `partner_id` (customer),
   `unit_id` (`ondelete='restrict'`), `project_id` (related to the unit, stored), `user_id` (sales
   agent, default current user), `company_id`, `currency_id`, `date` (contract date, [BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date.")),
   `confirmation_date`, `delivery_date`, `cancel_reason`, `price` (Monetary), `state`
   (`CONTRACT_STATE`: draft, confirmed, delivered, closed, cancelled; readonly, tracked).
3. [BR-08](../../../../docs/business-requirements.md#contracts "BR-08: The contract price is frozen at the unit's list price when the contract is created. Changing the unit's list price afterwards does not change existing contracts. If the unit is changed on a draft contract, the price is taken again from the new unit."): `price` computed from `unit_id` (`store=True`, `precompute=True`, readonly); it depends on
   `unit_id` only, so changing the unit on a draft re-takes the price, and changing the unit's list
   price later changes nothing.
4. Sequence: `ir.sequence` code `real.estate.contract`, prefix `NH/%(year)s/`, padding 5,
   `company_id` `False`, `noupdate`. Drawn in `create()` like `sale.order`, with the contract date
   (or today) as `sequence_date`.
5. ACL rows: agent RWCD (draft-only limits come in Step 8), collections R, manager RWCD,
   `account.group_account_invoice` R.
6. List, form (statusbar, `<chatter/>`), search views; menu Contracts.
7. `tests/common.py` (`RealEstateCommon`, fixtures in the Test Plan); T1 (contract part), T2, T7.
*Check:* `make test`; create a contract in the browser.

**Step 6 — Unit status from its contract** (unit model and views *(edit)*). *[BR-03](../../../../docs/business-requirements.md#projects-and-units "BR-03: A unit's status — available, reserved, sold, delivered — is derived from its contract and is never typed by hand: no live contract → available; draft contract → reserved; confirmed → sold; delivered or closed → delivered."), [AC-01.1](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.1: Given unit HNC-B07-0302 is available, when an agent creates a contract for it, then the contract is draft, gets a reference from the sequence, its price is 8,580,000 EGP, and the unit shows reserved.").*
1. Unit `contract_ids` (One2many). `state`: Selection available / reserved / sold / delivered,
   `compute`, `store=True`, never editable; depends on `contract_ids.state`; the live contract is the
   one not cancelled (draft → reserved, confirmed → sold, delivered or closed → delivered, none →
   available).
2. Unit list decorated by state; search filter by state.
3. T1 completed (unit shows reserved).
*Check:* `make test`.

**Step 7 — No double sale** (contract model *(edit)*, `tests/test_contract.py` *(edit)*). *[BR-04](../../../../docs/business-requirements.md#projects-and-units "BR-04: A unit can have at most one contract that is not cancelled. Creating a second one fails, whoever tries and in whatever order (the double-sale case). It is enforced in the database, so it holds even when two users save at the same moment."),
[AC-01.3](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.3: Given a unit already has a non-cancelled contract, when anyone creates a second contract for it, then it is refused with a message giving the existing contract's reference only.").*
1. **Database:** `_unit_live_unique = models.UniqueIndex("(unit_id) WHERE state != 'cancelled'",
   "This unit already has a contract that is not cancelled.")` — holds under concurrent saves.
2. **Friendly message:** before `super()` in `create()` and in `write()` when `unit_id` changes,
   search with `sudo()` for a live contract on the same unit and raise `ValidationError` naming
   **only** that contract's reference. Two contracts for one unit in the same `create()` call are
   caught too. `sudo()` because from Story 06 an agent cannot see the other contract.
3. T3, T4. Negative checks N1, N2.
*Check:* `make test`; second contract refused in the browser.

**Step 8 — Delete and edit limits** (contract model *(edit)*, tests *(edit)*). *[BR-13](../../../../docs/business-requirements.md#contracts "BR-13: A contract that is not draft cannot be deleted."), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."),
[AC-01.5](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.5: Given a draft contract, when the agent deletes it, then it is deleted and the unit is available. Given a confirmed contract, deleting it is refused.").*
1. [BR-13](../../../../docs/business-requirements.md#contracts "BR-13: A contract that is not draft cannot be deleted."): `@api.ondelete(at_uninstall=False)` `_unlink_except_draft` raising `UserError`.
2. Write guard: a user without the manager group cannot write a contract that is not draft;
   `unit_id` can change only on a draft.
3. T6.
*Check:* `make test`.

**Step 9 — Confirm** (contract model, form view *(edit)*, `tests/test_contract_states.py`).
*[US-10](../../../../docs/business-requirements.md#us-10--confirm-a-contract "US-10: Confirm a contract"), [BR-10](../../../../docs/business-requirements.md#contracts "BR-10: Only a sales manager can confirm a contract. Confirmation requires: a generated schedule whose down payment plus installments equal the contract price exactly, and the customer identity in BR-05."), [BR-05](../../../../docs/business-requirements.md#customers "BR-05: The customer is a contact (person or company). Each individual buyer has a nationality: Egyptian or foreign (a field on the contact — the address country does not say it). An Egyptian individual must have a national ID (الرقم القومي) before the contract can be confirmed; a foreign individual must have a passport number instead. A company buyer has no identity check in v1."), [BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date."), [AC-10.1](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.1: An agent cannot confirm a contract; a manager can."), [AC-10.2](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.2: Confirmation is refused if there is no schedule, if the schedule does not sum to the price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A company customer needs neither.") (identity), [AC-10.3](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.3: On confirmation the unit shows sold and every line already due is invoiced (BR-21).") (unit).*
1. `action_confirm()`: manager only (`has_group`, else `AccessError`); from draft only; identity
   check per [BR-05](../../../../docs/business-requirements.md#customers "BR-05: The customer is a contact (person or company). Each individual buyer has a nationality: Egyptian or foreign (a field on the contact — the address country does not say it). An Egyptian individual must have a national ID (الرقم القومي) before the contract can be confirmed; a foreign individual must have a passport number instead. A company buyer has no identity check in v1.") (individual: Egyptian → `national_id`, foreign → `passport_number`, no
   nationality → refused; company → nothing); contract date not after today, empty date → today;
   sets `confirmation_date`, state `confirmed`. Checks collected in `_confirmation_error_message()`,
   as in `sale.order`, where Story 03 adds the schedule check.
2. Confirm button, `groups` manager, visible on draft.
3. T11, T12, T13. Negative check N3.
*Check:* `make test`; confirm in the browser as manager.

**Step 10 — Deliver** (contract model, form view, tests *(edit)*). *[US-11](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "US-11: Record delivery of the unit"), [BR-11](../../../../docs/business-requirements.md#contracts "BR-11: Only a sales manager can mark a contract delivered, and only from confirmed. The delivery date is recorded. Installments continue after delivery as scheduled."), [AC-11.1](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.1: Only a confirmed contract can be marked delivered, only by a manager.").*
1. `action_deliver()`: manager only; from confirmed only; `delivery_date` = today if empty, never
   in the future; state `delivered`.
2. Deliver button, `groups` manager. T14.
*Check:* `make test`.

**Step 11 — Cancel** (contract model, `wizard/__init__.py`, `wizard/real_estate_contract_cancel.py`,
`wizard/real_estate_contract_cancel_views.xml`, ACL row, `__init__.py`, `__manifest__.py`, tests
*(edit)*). *[US-09](../../../../docs/business-requirements.md#us-09--cancel-a-contract "US-09: Cancel a contract"), [BR-32](../../../../docs/business-requirements.md#cancellation "BR-32: A draft contract can be cancelled by its agent with no consequences. A confirmed contract can be cancelled only by a manager, with a written reason. A delivered or closed contract cannot be cancelled in v1."), [AC-09.1](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.1: Given a draft contract, its agent can cancel it; the unit becomes available."), [AC-09.2](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.2: Given a confirmed contract, an agent cannot cancel it; a manager can, only with a reason."), [AC-09.5](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.5: A delivered contract cannot be cancelled.").*
1. `action_cancel()`: draft → cancelled at once, by its agent or a manager; confirmed → opens the
   wizard (manager only); delivered / closed → refused.
2. Wizard `real.estate.contract.cancel` (transient): `contract_id`, `reason` (required Text);
   `action_confirm_cancel()` stores `cancel_reason`, state `cancelled`. ACL: manager only.
3. No action reaches `closed` (Story 04's nightly job does). No `cancelled → draft`.
4. T8, T9, T10.
*Check:* `make test`; cancel a confirmed contract with a reason in the browser.

**Step 12 — Read-only roles** (`tests/test_access.py`). *[US-06](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "US-06: Agents see only their own contracts"), [BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts."), [AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule."), [AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.").*
Collections and accountants hold no write ACL on contracts, so every field — price included — is
read-only for them. No field-level `groups=` is needed yet; it is reconsidered when a later story
gives collections any write right. T15, T16. Negative check N4.
*Check:* `make test`.

**Step 13 — Whole flow + CI stack.** On `re_dev` as admin plus one agent and one manager created
by hand: create project, unit, customer, contract; confirm, deliver; second contract refused;
cancel with reason. Log stays clean. Then `make lint` and `make test-ci`.

**Step 14 — Docs + PR.** `docs/design-notes/02-core-models.md` (state machine, the two-layer [BR-04](../../../../docs/business-requirements.md#projects-and-units "BR-04: A unit can have at most one contract that is not cancelled. Creating a second one fails, whoever tries and in whatever order (the double-sale case). It is enforced in the database, so it holds even when two users save at the same moment."),
why ACLs now and record rules later, stored compute + `compute_sudo`, alternatives, negative
checks; 3 explain-back questions). `README.md` *(edit)*: status line; roadmap 01 → done, 02 → in
review. PR links this plan and ticks the Done Criteria; CI green; the maintainer merges with
"Create a merge commit"; explain-back answers in `docs/learning-log.md`.

## Edge Cases & Failure Modes

1. **Race on [BR-04](../../../../docs/business-requirements.md#projects-and-units "BR-04: A unit can have at most one contract that is not cancelled. Creating a second one fails, whoever tries and in whatever order (the double-sale case). It is enforced in the database, so it holds even when two users save at the same moment.").** Two users pass the Python check at once; the second `INSERT` waits on the
   unique index, then fails. The request layer turns the `IntegrityError` into a `ValidationError`
   with the index message (not the reference — the first contract was not visible yet).
2. **Python check without `sudo()`** would miss a contract hidden by Story 06's rules and leak the
   raw database error instead. The check uses `sudo()` and returns the reference only — no
   customer, agent or price ([AC-01.3](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.3: Given a unit already has a non-cancelled contract, when anyone creates a second contract for it, then it is refused with a message giving the existing contract's reference only.")).
3. **Cancelled contracts do not block.** The index's `WHERE state != 'cancelled'` lets a unit be
   resold after a cancel; a test proves it.
4. **Database-index test breaks the transaction.** The expected `IntegrityError` is raised inside
   `assertRaises` (savepoint) and under `mute_logger('odoo.sql_db')`, so the test cursor survives and
   the log check sees no `ERROR`.
5. **Price drift.** If `price` depended on `unit_id.list_price`, [AC-01.2](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.2: Given the unit's list price is then changed to 9,000,000, when the agent reopens the contract, then its price is still 8,580,000.") would fail. It depends on
   `unit_id` only.
6. **Unit status as admin only.** The stored compute runs as superuser (`compute_sudo`), so it is
   right whoever triggers it, and stays right after Story 06.
7. **Unit status hand-edited** — field is computed and readonly; never in an import column (Story 10).
8. **Writes after confirmation.** Agents are blocked by the write guard; managers may still edit
   ([BR-35](../../../../docs/business-requirements.md#visibility "BR-35: A sales agent sees only contracts where they are the agent, and their schedules, and edits them only while draft. A sales manager sees and edits all contracts, bills late fees and records cheques. A collections officer reads all contracts and schedules, bills late fees and records cheques, but cannot change prices, plans or schedules; billing goes through the module's own action, so the officer needs no general invoicing rights. An accountant reads all contracts and schedules and edits none. Agents see the cheques on their own contracts.")), but `unit_id` is locked outside draft for everyone.
9. **National ID edge values.** Non-digits, 13 or 15 digits, first digit 1 or 4, 29 February in a
   non-leap year, a date after today. [AC-01.4](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.4: Given a customer's national ID is 29901158800017 (born 15 Jan 1999), the system accepts it; given 19901158800017 (first digit 1), 29902308800017 (30 February) or 33001018800017 (born 1 Jan 2030, in the future), the system refuses it.")'s "future" fixture (born 2030) is tested with today
   frozen (`freezegun`) so it does not start passing in 2030.
10. **Identity on a company contact.** Companies skip the check ([BR-05](../../../../docs/business-requirements.md#customers "BR-05: The customer is a contact (person or company). Each individual buyer has a nationality: Egyptian or foreign (a field on the contact — the address country does not say it). An Egyptian individual must have a national ID (الرقم القومي) before the contract can be confirmed; a foreign individual must have a passport number instead. A company buyer has no identity check in v1.")); an individual with no
    nationality is refused at confirmation.
11. **Contract date after confirmation day** is refused at confirmation ([BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date.")); an empty date
    becomes the confirmation date.
12. **Sequence year.** Taken from the contract date (or today), like `sale.order`. Prefix `NH/`
    matches [BR-07](../../../../docs/business-requirements.md#contracts "BR-07: A contract links one customer, one unit, one sales agent and one payment plan, and gets a reference from a sequence, e.g. NH/2027/00042. Its contract date is set on the draft and cannot be later than the day it is confirmed; if left empty, it becomes the confirmation date."); the record is `noupdate`, so a company changes it in Settings → Sequences.
13. **Multi-company.** `check_company=True` refuses a unit and contract of different companies;
    `company_id` on every model is ready for Story 06's rules.
14. **Deleting a project or unit in use** — `ondelete='restrict'` refuses it.
15. **Manager also accountant** — ACLs add up; nothing breaks.
16. **Agents still see all contracts** until Story 06 — known, written in the design note and the PR.
17. **Admin-only tests hide ACL gaps.** Fixtures are created in `setUpClass`, but every action under
    test runs `with_user()` an agent, manager, collections or Invoicing user from `new_test_user`.
18. **Log warnings from new data files** (e.g. a view field that does not exist, a missing ACL on
    the wizard) fail `make test` through the log check.

## Test Plan

Tests under `addons/real_estate_eg/tests/`, all `@tagged("post_install", "-at_install")`. Shared
fixtures in `common.py` (`RealEstateCommon`): users agent A, agent B, manager, collections officer,
accountant (`account.group_account_invoice`); project HNC; units `HNC-B07-0302` (3-bedroom, 165 m²,
8,580,000) and a 2-bedroom HNC unit (125 m², 6,500,000); customers: Egyptian with a valid national
ID, Egyptian without one, foreign with a passport, a company.

| # | Test | Proves |
|---|---|---|
| T1 | `test_contract.py` — `test_ac_01_1_create_reserves_unit` | [AC-01.1](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.1: Given unit HNC-B07-0302 is available, when an agent creates a contract for it, then the contract is draft, gets a reference from the sequence, its price is 8,580,000 EGP, and the unit shows reserved.") |
| T2 | `test_contract.py` — `test_ac_01_2_price_frozen` | [AC-01.2](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.2: Given the unit's list price is then changed to 9,000,000, when the agent reopens the contract, then its price is still 8,580,000.") |
| T3 | `test_contract.py` — `test_ac_01_3_second_contract_refused` (agent B, after agent A; message has the reference and no customer name) | [AC-01.3](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.3: Given a unit already has a non-cancelled contract, when anyone creates a second contract for it, then it is refused with a message giving the existing contract's reference only.") |
| T4 | `test_contract.py` — `test_ac_01_3_database_blocks_double_sale` (SQL update re-activates a cancelled contract → `IntegrityError`) and `test_cancelled_contract_frees_unit_for_resale` | [AC-01.3](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.3: Given a unit already has a non-cancelled contract, when anyone creates a second contract for it, then it is refused with a message giving the existing contract's reference only.") / [BR-04](../../../../docs/business-requirements.md#projects-and-units "BR-04: A unit can have at most one contract that is not cancelled. Creating a second one fails, whoever tries and in whatever order (the double-sale case). It is enforced in the database, so it holds even when two users save at the same moment.") in the database |
| T5 | `test_partner.py` — `test_ac_01_4_national_id` (the four fixtures + edge values above) | [AC-01.4](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.4: Given a customer's national ID is 29901158800017 (born 15 Jan 1999), the system accepts it; given 19901158800017 (first digit 1), 29902308800017 (30 February) or 33001018800017 (born 1 Jan 2030, in the future), the system refuses it.") |
| T6 | `test_contract.py` — `test_ac_01_5_delete_draft_only` | [AC-01.5](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.5: Given a draft contract, when the agent deletes it, then it is deleted and the unit is available. Given a confirmed contract, deleting it is refused.") |
| T7 | `test_contract.py` — `test_ac_01_6_unit_change_retakes_price` | [AC-01.6](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.6: Given a draft contract for HNC-B07-0302 at 8,580,000, when the agent changes the unit to a 2-bedroom HNC unit, then the price becomes 6,500,000.") |
| T8 | `test_contract_states.py` — `test_ac_09_1_agent_cancels_draft` | [AC-09.1](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.1: Given a draft contract, its agent can cancel it; the unit becomes available.") |
| T9 | `test_contract_states.py` — `test_ac_09_2_cancel_confirmed_manager_with_reason` | [AC-09.2](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.2: Given a confirmed contract, an agent cannot cancel it; a manager can, only with a reason.") |
| T10 | `test_contract_states.py` — `test_ac_09_5_delivered_cannot_be_cancelled` | [AC-09.5](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.5: A delivered contract cannot be cancelled.") |
| T11 | `test_contract_states.py` — `test_ac_10_1_only_manager_confirms` | [AC-10.1](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.1: An agent cannot confirm a contract; a manager can.") |
| T12 | `test_contract_states.py` — `test_ac_10_2_identity_required` | [AC-10.2](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.2: Confirmation is refused if there is no schedule, if the schedule does not sum to the price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A company customer needs neither.") (identity part) |
| T13 | `test_contract_states.py` — `test_ac_10_3_confirm_marks_unit_sold` | [AC-10.3](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.3: On confirmation the unit shows sold and every line already due is invoiced (BR-21).") (unit part) |
| T14 | `test_contract_states.py` — `test_ac_11_1_deliver_confirmed_by_manager_only` | [AC-11.1](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.1: Only a confirmed contract can be marked delivered, only by a manager.") |
| T15 | `test_access.py` — `test_ac_06_3_collections_reads_cannot_edit` | [AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule.") |
| T16 | `test_access.py` — `test_ac_06_5_accountant_reads_cannot_edit` | [AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.") |
| T17 | `make test`, `make lint`, `make test-ci`, CI on the PR and on `main` | gates stay green |

**Negative checks** (seen failing once, then undone before `git add`; results in the design note):

- N1: drop the `WHERE` clause from the unique index → `test_cancelled_contract_frees_unit_for_resale` fails.
- N2: make `price` depend on `unit_id.list_price` → T2 fails.
- N3: remove the manager check from `action_confirm` → T11 fails.
- N4: give collections write on contracts in the CSV → T15 fails.

## Verification Steps

```bash
git switch main && git pull --rebase && git switch -c story/02-core-models
make test        # all T1–T16 pass, log clean
make lint        # pre-commit green
make test-ci     # same tests in the CI Docker stack
make run         # Step 13 walk-through on re_dev; log clean
gh pr checks     # pre-commit + test green on the PR
gh run list --branch main --limit 1   # green after merge
```

## Done Criteria

- [ ] **[AC-01.1](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.1: Given unit HNC-B07-0302 is available, when an agent creates a contract for it, then the contract is draft, gets a reference from the sequence, its price is 8,580,000 EGP, and the unit shows reserved.")** An agent creates a contract for available unit `HNC-B07-0302`: it is draft, gets a
  sequence reference, its price is 8,580,000 EGP, and the unit shows **reserved**. *Proof:* T1.
- [ ] **[AC-01.2](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.2: Given the unit's list price is then changed to 9,000,000, when the agent reopens the contract, then its price is still 8,580,000.")** After the unit's list price changes to 9,000,000, the contract's price is still
  8,580,000. *Proof:* T2.
- [ ] **[AC-01.3](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.3: Given a unit already has a non-cancelled contract, when anyone creates a second contract for it, then it is refused with a message giving the existing contract's reference only.")** A second non-cancelled contract on the same unit is refused, by anyone and in any
  order, with a message giving only the existing contract's reference; the database enforces it.
  *Proof:* T3, T4.
- [ ] **[AC-01.4](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.4: Given a customer's national ID is 29901158800017 (born 15 Jan 1999), the system accepts it; given 19901158800017 (first digit 1), 29902308800017 (30 February) or 33001018800017 (born 1 Jan 2030, in the future), the system refuses it.")** National ID `29901158800017` is accepted; `19901158800017`, `29902308800017` and
  `33001018800017` are refused. *Proof:* T5.
- [ ] **[AC-01.5](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.5: Given a draft contract, when the agent deletes it, then it is deleted and the unit is available. Given a confirmed contract, deleting it is refused.")** An agent deletes a draft contract and the unit is available again; deleting a
  confirmed contract is refused. *Proof:* T6.
- [ ] **[AC-01.6](../../../../docs/business-requirements.md#us-01--create-a-contract-for-an-available-unit "AC-01.6: Given a draft contract for HNC-B07-0302 at 8,580,000, when the agent changes the unit to a 2-bedroom HNC unit, then the price becomes 6,500,000.")** Changing a draft contract's unit to a 2-bedroom HNC unit sets its price to
  6,500,000. *Proof:* T7.
- [ ] **[AC-09.1](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.1: Given a draft contract, its agent can cancel it; the unit becomes available.")** An agent cancels their draft contract; the unit becomes available. *Proof:* T8.
- [ ] **[AC-09.2](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.2: Given a confirmed contract, an agent cannot cancel it; a manager can, only with a reason.")** An agent cannot cancel a confirmed contract; a manager can, only with a reason.
  *Proof:* T9.
- [ ] **[AC-09.5](../../../../docs/business-requirements.md#us-09--cancel-a-contract "AC-09.5: A delivered contract cannot be cancelled.")** A delivered contract cannot be cancelled. *Proof:* T10.
- [ ] **[AC-10.1](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.1: An agent cannot confirm a contract; a manager can.")** An agent cannot confirm a contract; a manager can. *Proof:* T11.
- [ ] **[AC-10.2](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.2: Confirmation is refused if there is no schedule, if the schedule does not sum to the price, or if an individual customer lacks a national ID (Egyptian) or passport number (foreign). A company customer needs neither.")** *(identity part)* Confirmation is refused when an individual customer lacks a
  national ID (Egyptian) or passport number (foreign); a company customer needs neither. The
  schedule check is Story 03. *Proof:* T12.
- [ ] **[AC-10.3](../../../../docs/business-requirements.md#us-10--confirm-a-contract "AC-10.3: On confirmation the unit shows sold and every line already due is invoiced (BR-21).")** *(unit part)* On confirmation the unit shows **sold**. Invoicing is Story 04.
  *Proof:* T13.
- [ ] **[AC-11.1](../../../../docs/business-requirements.md#us-11--record-delivery-of-the-unit "AC-11.1: Only a confirmed contract can be marked delivered, only by a manager.")** Only a confirmed contract can be marked delivered, and only by a manager.
  *Proof:* T14.
- [ ] **[AC-06.3](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.3: A collections officer sees all contracts but cannot edit price, plan or schedule.")** A collections officer sees all contracts but cannot edit price, plan or schedule —
  enforced by access rights here (read-only ACL); record rules come in Story 06. *Proof:* T15.
- [ ] **[AC-06.5](../../../../docs/business-requirements.md#us-06--agents-see-only-their-own-contracts "AC-06.5: An accountant sees all contracts and schedules but cannot edit them.")** An accountant sees all contracts but cannot edit them (schedules are Story 03).
  *Proof:* T16.
