# 02 — Core models, views, states and access rights

Plan: [`.squad/plans/installments/02-core-models/plan.md`](../../.squad/plans/installments/02-core-models/plan.md)

Story 02 builds the three core models — project, unit, contract — the customer's identity on
the contact, the contract's state machine, and the security groups with their access rights.
A unit can now be reserved, sold, delivered and released again, and every rule is tested as a
real non-admin user.

## The models

| Model | Holds | Rules |
|---|---|---|
| `real.estate.project` | name, code, location, expected delivery, company | code unique per company |
| `real.estate.unit` | code, project, type, bedrooms, area, floor, list price, price per m², **status** | BR-01, BR-02, BR-03 |
| `real.estate.contract` | reference, customer, unit, sales agent, contract / confirmation / delivery dates, price, state, cancel reason; chatter | BR-04, BR-07 – BR-13, BR-32 |
| `res.partner` *(extended)* | nationality, national ID, passport number | BR-05, BR-06 |
| `real.estate.contract.cancel` *(transient)* | the "reason" dialog for cancelling a confirmed contract | BR-32 |

**Odoo hygiene, from the first model.** Every model carries `company_id` and `currency_id`;
money is `fields.Monetary`; the contract reference comes from an `ir.sequence`; the contract
has chatter (`mail.thread`, `mail.activity.mixin`); a unit takes its company from its project
and a contract from its unit, so the three can never disagree.

## The contract state machine

The shape is borrowed from `sale.order` (`odoo-src/odoo/addons/sale/models/sale_order.py`):
a `state` selection that is read-only on the form, public `action_*` methods behind the
buttons, and `_confirmation_error_message()` collecting every reason a contract cannot be
confirmed.

| Action | Who | From | Checks | Unit becomes |
|---|---|---|---|---|
| create | agent or manager | — | unit free (BR-04) | reserved |
| `action_confirm` | manager | draft | contract date not after today; customer identity (BR-05) | sold |
| `action_deliver` | manager | confirmed | delivery date not in the future, not before the contract date | delivered |
| `action_cancel` | its agent or a manager | draft | — | available |
| `action_cancel` → dialog | manager | confirmed | written reason required | available |
| — | — | delivered, closed | cancelling is refused | — |

`closed` exists but no button reaches it: Story 04's nightly job closes a delivered contract
once everything is paid (BR-12). Story 03 adds the schedule check to
`_confirmation_error_message()`.

**Unit status is never typed.** It is a stored computed field depending on
`contract_ids.state` (BR-03). Stored, so units can be filtered and grouped by status; computed
as superuser (`compute_sudo`, on by default for stored computed fields), so it stays right
after Story 06 hides other agents' contracts.

**The price is frozen by its dependency.** `price` is computed from `unit_id` only — not from
`unit_id.list_price`. Changing the unit on a draft re-takes the price (AC-01.6); changing the
unit's list price later reaches no existing contract (AC-01.2).

## No double sale: two layers (BR-04)

1. **The database.** `models.UniqueIndex("(unit_id) WHERE state != 'cancelled'")` — a
   partial unique index. Postgres refuses a second live contract on a unit, even when two
   users save at the same moment and no Python code could see the other transaction. The
   `WHERE` clause lets a cancelled contract free the unit for resale.
2. **A clear message.** Before saving, `create()` and `write()` search for a live contract
   on the unit and refuse with *"Unit HNC-B07-0302 already has contract NH/2026/00001."* —
   the reference only, no customer or price (AC-01.3). The search runs with `sudo()`: from
   Story 06 an agent cannot see a colleague's contract, but the unit is still taken.

The index is the guarantee; the check is the user experience. In the race case the second
user gets the index's own message, raised by Odoo as a `ValidationError`.

## Security: who does what

| | Agent | Collections | Manager | Accountant (`account.group_account_invoice`) |
|---|---|---|---|---|
| Projects, units | read | read | full | read |
| Contracts | read, write, create, delete | read | full | read |
| Cancel dialog | — | — | full | — |

Three groups under one **Real Estate** privilege, Odoo 19's way of grouping roles in the
user form (`res.groups.privilege`). The manager implies agent and collections officer.
Accountants keep Odoo's own Invoicing group, which gets read access.

Access rights (`ir.model.access.csv`) work on whole tables. The finer rules sit in Python:

- an agent edits a contract only while it is draft; the unit is fixed once a contract leaves
  draft (`write()`);
- confirm, deliver and cancelling a confirmed contract check the manager group
  (`_check_manager()`), so an agent calling the method directly gets an `AccessError`, not
  just a hidden button;
- only drafts can be deleted, by anyone (`@api.ondelete`, as `sale.order` does) — BR-13;
- anyone who can read a contract may log a note on it (`_mail_post_access = "read"`, as
  `sale.order` does), so a collections officer can record a follow-up without edit rights.

**What waits for Story 06.** Record rules (`ir.rule`) decide *which rows* a user sees. Until
then an agent sees every agent's contracts and can edit another agent's draft, and a user of
company 2 sees company 1's records. `company_id` is already on every model for that story.

## Customer identity (BR-05, BR-06)

`nationality`, `national_id` and `passport_number` extend `res.partner`, hidden for companies.
A national ID is checked on every save: 14 ASCII digits (`[0-9]`, because `\d` would also
accept Arabic-Indic digits), first digit 2 or 3, digits 2–7 a real date of birth
(`datetime.date` refuses 30 February) that is not in the future. The identity requirement
itself — national ID for an Egyptian, passport for a foreigner, nothing for a company — is
checked at confirmation, because a draft may be started before the papers are in.

## Tests

22 tests, all run as users created by `new_test_user` (agent A, agent B, manager, collections
officer, accountant) — never as admin. Each Done Criterion has a named test
(`test_ac_01_1_…` to `test_ac_06_5_…`), plus tests for the contract date, the delivery date,
edit rights, draft-only confirmation and resale after cancellation. The national ID test runs
with today frozen (`freezegun`), so "born in 2030" stays in the future.

**The gates were seen failing** (each change undone before committing):

| Check | Change | Result |
|---|---|---|
| N1 | unique index without its `WHERE` clause | the database and resale tests error |
| N2 | price depends on `unit_id.list_price` | `test_ac_01_2_price_frozen` fails |
| N3 | no manager check in `action_confirm` | `test_ac_10_1_only_manager_confirms` fails |
| N4 | collections officer given write rights | `test_ac_06_3_…` fails on draft price, draft customer, create, delete |
| — | national ID date check disabled | `test_ac_01_4_national_id` fails (born 2030, born tomorrow) |
| — | delete rule disabled | `test_ac_01_5_delete_draft_only` fails |
| — | `_mail_post_access` removed | the collections officer cannot log a note |

N4 first **passed**: the test only edited a confirmed contract, which the Python edit guard
already blocks, so it never reached the access rights. A draft contract was added to the
test, and N4 then failed as it should. A negative check that passes means the test does not
test what its name says.

## Open questions

- **Duplicate national IDs.** Two contacts can carry the same national ID; no rule forbids
  it. A national ID belongs to one person, so a uniqueness rule (per company?) is likely
  wanted, but it is a business decision and a new `BR`, not a Story 02 change.
- **Sequence gaps.** The reference sequence uses Postgres sequences: a cancelled transaction
  still consumes its number, so references can have gaps. Accepted, as in core Odoo; a
  gap-free sequence would serialise every contract creation.

## Alternatives considered

- **A Python `@api.constrains` alone for BR-04.** Runs after the insert, cannot see another
  user's uncommitted contract, and would need `sudo()` once record rules exist. Rejected as
  the only layer; kept as the friendly message in front of the index.
- **A plain `UNIQUE (unit_id)` plus an `active` flag on contracts.** Cancelled contracts
  would have to be archived to free the unit, hiding history. The partial index keeps every
  contract visible.
- **A unit status typed by users, or written by each action.** Would drift from the
  contracts. The stored compute cannot.
- **A record rule for "agents edit only drafts".** Clean, but record rules are Story 06's
  subject; a few lines in `write()` cover it now and the test stays valid later.
- **Field-level `groups=` on the price.** Not needed while collections and accountants have
  no write right at all; reconsidered if a later story gives them one.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-02--core-models-views-states-and-access-rights).

1. BR-04 is enforced twice: a unique index in the database and a check in Python. What does
   each layer catch that the other cannot, and why does the Python check use `sudo()`?
2. The contract price is computed with `@api.depends("unit_id")`, not
   `@api.depends("unit_id.list_price")`. What would go wrong with the second, and which two
   acceptance criteria prove the choice?
3. Today an agent cannot confirm a contract, a collections officer cannot edit one, and an
   agent can still see other agents' contracts. Which mechanism is responsible for each of
   the three, and what will Story 06 add?
