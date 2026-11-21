# Real Estate Installment & Collections (Egypt) — Odoo 19 module

## Context

Real estate is the sector Egyptian Odoo partners name most often, because property is sold on long
installment plans — down payment, years of scheduled payments, maintenance deposit, delivery
milestones, late fees — and Odoo core has no concept of any of it. Every partner rebuilds it. The
public modules that exist are generic or foreign (one ships a Bangladeshi payment gateway). Nothing
is shaped for Egyptian practice.

`real_estate_eg` fills that gap. It is Odoo-core heavy on purpose: models, inheritance, computed
fields, states, record rules, cron, wizards, QWeb, accounting integration. A REST layer can come
later as a separate project — the business module first, then exposing it.

**Outcome:** a public, installable, tested Odoo 19 addon with a real spec behind it, demo data, a
bilingual contract PDF, and design notes a technical reader can follow.

---

## Decisions made

| Decision | Choice | Why |
|---|---|---|
| Odoo version | **19.0** | 18.0 standard support ends Sep 2027; 19.0 runs to Sep 2028. 19 keeps the classic `ir.model.access` + `ir.rule` security model that most production deployments still use; 20 merges them into `ir.access`. |
| Dev environment | **Odoo source + Python venv + local Postgres 16** | The common setup in Odoo partner shops, and what Odoo.sh mirrors. Allows debugger breakpoints inside core code. Docker is used for CI only. |
| Repo | One folder, `odoo-real-estate-eg/`, which **is** the git repo | Everything in one place; the Odoo source is cloned inside it and gitignored. |
| AI disclosure | **Stated openly in the README**: built with AI assistance, every line reviewed, mistakes caught logged in `docs/learning-log.md` | Commits carry a co-author line anyway. The mistake log is the proof of review. |
| Method | **squad-kit 0.x-style spec artifacts, written by hand**, in `.squad/` | A spec-driven workflow: each stage is one story with an intake and a plan file whose Done Criteria become the tests. |
| Who builds | **An AI assistant implements each plan; the maintainer reviews and merges every PR** | Authorship must be defensible: the maintainer writes the two core pieces (below) and passes an explain-back gate on every story. |
| Spec timing | **Whole business document written at Stage 0**, then living | Ch.1 (the MVP) can't be right until domain, actors and flows are written down, and the company chapter produces the demo data and test numbers. Amended later via small commits + ADRs. |
| Domain anchor | Invented developer **Nile Heights Developments** (نايل هايتس للتطوير العقاري) | Concrete price lists and schedules make every rule checkable, and the numbers become demo data and test fixtures for free. |

**Invented data only.** No real company material, no client names, no real contacts.

---

## Method: spec artifacts, by hand

Each build story (01–10) gets an artifact pair. Intakes are per **build story**, not per user story:
an intake's acceptance criteria quote the `US-xx` / `BR-xx` it covers from the business document, so
the trace runs BR → US → intake → plan → test.

```
.squad/
  config.yaml
  stories/installments/<story-id>/intake.md     # Title, Description, Acceptance criteria,
                                                # Dependencies, Technical hints, Out of scope
  plans/
    00-index.md                                 # feature slugs
    installments/
      00-overview.md                            # table: file, title, depends on
      01-env-skeleton/plan.md                   # one folder per story, same name as its intake
      02-core-models/plan.md
      …
```

Each plan file uses these headings, verbatim:

`## Prerequisites` → `## Story Goal` → `## Context — Read These Files First` →
`## Implementation tasks` → `## Edge Cases & Failure Modes` → `## Test Plan` →
`## Verification Steps` → `## Done Criteria`

Two rules are load-bearing and kept strictly: **no invented paths, line numbers or symbols** —
everything cited must come from a file actually read — and **`## Edge Cases & Failure Modes` and
`## Test Plan` are mandatory**, never skipped as "obvious".

---

## How we work, per stage

1. **Write the story** — intake + plan file, committed to `main` before any code. The maintainer
   approves the Done Criteria.
2. **Teaching brief** — the Odoo concept the stage uses is explained before anything is written.
3. **Branch `story/NN-<slug>`** and implement the plan in small commits.
4. **Tests** derived from the Done Criteria, green.
5. **`docs/design-notes/NN-<topic>.md`** — why it's built this way, what the alternatives were.
   These become the README's design-notes section.
6. **Open a PR** whose description links the plan file and ticks its Done Criteria. CI must be green.
   The maintainer reviews and merges it.
7. **Explain-back gate** — each design note ends with 3 questions; the maintainer answers them in
   their own words in `docs/learning-log.md`. The next story doesn't start until it's done.

**Why a PR per story and not commits to `main`:** ten reviewed PRs, each tied to a written plan
with a test plan, show the process, not just the result.

`docs/learning-log.md` also carries the AI-mistake log: every time the assistant gets Odoo wrong and
the review catches it, it goes in.

**Parts the maintainer writes personally:**
- the installment schedule arithmetic and its rounding (Story 03)
- the agent-sees-own record rule and its test (Story 06)

---

## Target layout

```
odoo-real-estate-eg/                    # the repo — everything inside
├── README.md  LICENSE  CHANGELOG.md    # LGPL-3, matching Odoo addons
├── .gitignore                          # odoo-src/, venv/, *.conf; .squad is committed
├── .gitattributes                      # * text=auto eol=lf
├── odoo-src/odoo/                      # Odoo 19 shallow clone — NOT committed
├── venv/                               # NOT committed
├── .squad/                             # stories + plans, as above
├── docs/
│   ├── business-requirements.md        # Stage 0 — the chaptered business document
│   ├── technical-design.md             # rules → models, fields, methods
│   ├── design-notes/                   # one per story
│   ├── decisions/                      # ADR-001.md … one decision each
│   └── learning-log.md
├── addons/real_estate_eg/
│   ├── __manifest__.py  __init__.py
│   ├── models/  wizard/  views/  security/  report/
│   ├── data/    demo/    tests/   i18n/
│   └── static/description/             # icon.png + screenshots
├── .github/workflows/ci.yml
├── docker/docker-compose.ci.yml
├── odoo.conf.example
├── requirements-dev.txt
├── .pre-commit-config.yaml
└── Makefile                            # make run / make test / make shell
```

Module technical name: **`real_estate_eg`** — distinct from the core `estate` tutorial module and from
the existing public `re_installment`.

---

## Stage 0 — Business document and story intakes (no code)

**This is the gate on everything else.**

`docs/business-requirements.md`, one file, chapters:

- **Ch.1 — MVP (v1).** The build contract: user stories `US-01…` with Given/When/Then acceptance
  criteria, each traceable to a numbered business rule `BR-01…`. These become the intakes.
- **Ch.2 — Domain primer.** How an Egyptian developer actually sells a unit, end to end — including
  **post-dated cheques (شيكات آجلة)**: the buyer typically hands over cheques for the whole schedule at
  signing, and collections is largely tracking each cheque (in hand → deposited → cleared / bounced).
  This is the most Egypt-specific thing in the domain and no public module models it.
- **Ch.3 — Glossary, Arabic + English.** مشروع / وحدة / عقد / مقدم / قسط / وديعة صيانة / غرامة تأخير / تسليم.
- **Ch.4 — Actors and roles.** Sales agent, sales manager, collections officer, accountant, customer.
- **Ch.5 — Process flows.** Reservation → contract → schedule → invoicing → collection → delivery →
  close, plus cancellation and refund. State machines for contract and installment line.
- **Ch.6 — Nile Heights Developments.** The invented company: three projects (Horizon New Cairo,
  Palm Shores Sahel, Capital Business Park), unit types, price lists, standard plans — e.g. 10% down,
  8 years quarterly, 8% maintenance deposit due at delivery, 1%/month late fee after a 7-day grace.
  These exact numbers become `demo/` and the test fixtures.
- **Ch.7 — Beyond v1.** Broker commissions, resale and transfer, customer portal, payment gateways,
  multi-currency, **ETA e-invoicing** — each with why it's deferred and what it would touch.
- **Ch.8 — Open business questions** to decide before Story 02 (answered 2026-11-21, after an
  independent review). At least: post-dated cheque
  tracking in v1 or v1.1; invoice per installment on its due date vs one receivable at signing; late
  fee simple vs compounding, and capped or not; what a cancellation refunds.

Then `.squad/stories/installments/*/intake.md` for all ten stories, and
`.squad/plans/installments/00-overview.md`.

**Done when:** Ch.1 read alone says "yes, that is the business", and every acceptance criterion is
specific enough to write a test against.

---

## Stories 01–10 — Build

| # | Story | Covers | Delivers | Done Criteria headline |
|---|---|---|---|---|
| 01 | **Environment + skeleton** | — | Odoo 19 cloned, venv, Postgres role, `odoo.conf`, Makefile, repo pushed, `.gitattributes`, `real_estate_eg` installs empty, **OCA pre-commit stack** (`ruff`, `pylint-odoo`, `oca-fix-manifest`, XML/CSV formatters) + CI green | `make run` serves Odoo 19 and the module installs from Apps |
| 02 | **Core models + views** | US-01, US-09 | `real.estate.project`, `real.estate.unit`, `real.estate.contract`; list/form/search views, menus; states draft→confirmed→delivered→closed + cancelled; `mail.thread` chatter. **Odoo hygiene from day one:** contract reference from `ir.sequence`, `company_id` + `currency_id` on every model, `Monetary` fields, `@api.ondelete` blocking deletion of a confirmed contract, **a constraint allowing only one active contract per unit** (the double-sale case). **Groups + ACLs (`ir.model.access.csv`) land here**, so every test from now on runs as a real agent or manager user, never as admin | A project, unit and contract are created in the UI and moved through their states; confirming a second contract on a sold unit fails |
| 03 | **Schedule generator** *(maintainer writes the arithmetic)* | US-02 | `real.estate.plan.template`, `real.estate.installment`, transient wizard: down payment + N installments, monthly/quarterly, rounding difference onto the last line, maintenance deposit as its own scheduled amount | Tests cover an ugly rounding case and prove installments sum exactly to the unit price, with the maintenance deposit scheduled separately |
| 04 | **Accounting link** | US-03 | Service products per charge type in `data/`; each installment generates an `account.move` on its due date, posted to a customer-advances account with no taxes; journals use an outstanding receipts account so payments reduce the amount due at once; computed `amount_paid` / `outstanding` reading real payment state. Tests built on Odoo's `AccountTestInvoicingCommon`, which sets up a company with a chart of accounts — not hand-rolled accounting fixtures | Every journal entry traces from contract → invoice → payment and can be found in the DB |
| 05 | **Overdue cron + late fees** | US-05 | `ir.cron` flagging overdue lines past the grace period; late fee **computed from payment history** (not added night by night), rate and cap as company settings | **Running the cron twice produces the same result** — idempotency explicitly tested |
| 06 | **Record rules** *(maintainer writes the agent rule)* | US-06 | Groups and ACLs already exist from Story 02; this story adds the `ir.rule` restricting agents to their own contracts and installments, plus the standard multi-company rule on `company_id` | A test proves agent B gets an `AccessError` reading agent A's contract, and a user in company 2 can't see company 1's |
| 07 | **Collections views + performance** | US-04 | Due-this-month and overdue list views, aging-bucket pivot, graph, saved filters. **Then: generate ~1M installment lines with SQL `generate_series`, `EXPLAIN (ANALYZE, BUFFERS)` the collections query, add the index, measure again, write the before/after in the design note** — at 50k rows Postgres would seq-scan happily and the index would prove nothing | A collections officer answers "what do I chase today" in one click, and the query plan is explained in the design note |
| 08 | **Bilingual contract PDF** | US-07 | QWeb report, paper format, Arabic and English **side by side on the same page** (that is what Egyptian contracts look like — not Odoo's translation system), an Arabic font (e.g. Noto Naskh Arabic) installed locally and in the CI image; `i18n/ar.po` for the UI separately | The Arabic PDF renders correctly — joined letters, right-to-left — and survives a 60-character customer name |
| 09 | **Post-dated cheques** *(stretch)* | US-13 | Cheque records linked to schedule lines, states held → deposited → cleared / bounced, replacement of a bounced cheque, "To deposit" list. Status only — no accounting | A bounced cheque is replaced and its history kept; marking a cheque cleared never changes payment status. **If time runs short, this moves to v1.1** |
| 10 | **Ship** | US-08 | Demo data from Ch.6, a unit import wizard for ~200 units (re-runnable without duplicating, all-or-nothing), README with screenshots, **a 60-second demo GIF**, design notes, **coverage report + test count in the README**, `v1.0.0` tag | A new user installs and clicks through in two minutes; the full flow demos in five minutes without notes |

**If time runs short, cut features — never the tests or the README.**

> **Superseded mapping:** the "Covers" column above was drafted before the business document. The
> authoritative user-story → build-story map is `business-requirements.md` §1.4 (US-01…US-13).

---

## Reuse, not reinvention

| Need | Use | Not |
|---|---|---|
| Customer | `res.partner` | a custom customer model |
| Invoice + payment state | `account.move`, `account.payment` | custom payment tracking |
| Chatter, activities | `mail.thread`, `mail.activity.mixin` | custom notes |
| Scheduling | `ir.cron` | an external scheduler |
| Permissions | groups + `ir.rule` | `sudo()` and manual checks |
| Egypt chart of accounts | `l10n_eg` | hand-built accounts |

**One decision to record as an ADR in Story 04:** whether `l10n_eg` goes in `depends` or stays a
documented recommendation. Hard-depending on a localization makes the module refuse to install on a
database with a different chart of accounts. The likely answer is: don't depend on it, work with any
chart of accounts, and say so in the README.

Story 02's `## Context — Read These Files First` will point at
`odoo-src/odoo/addons/sale/models/sale_order.py` — the contract borrows its state/confirm/cancel
shape, so it matches core conventions.

---

## Explicitly not in v1

Payment gateway integration, ETA submission, broker commission calculation, customer portal,
multi-currency, resale/transfer. Listed in README as "possible next", with ETA named correctly
(`l10n_eg_edi_eta`, OAuth2 client-credentials, preprod vs production hosts).

---

## Verification

Per story, from its `## Verification Steps`:
```bash
make test        # odoo -d re_test -i real_estate_eg --test-enable --stop-after-init
```
CI runs the same in Docker against Postgres on every push.

Test rules for every story: tests build their own fixtures and **never rely on demo data**; they run as
agent/manager users, not admin; and Done Criteria items map one-to-one to named tests.

End to end, before tagging v1.0.0:
1. Fresh database, install `real_estate_eg` with demo data — no errors, no warnings in the log.
2. Create a contract for a Horizon New Cairo unit, generate a 10%/8-year quarterly plan, confirm it.
3. Check the schedule sums exactly to the unit price plus maintenance deposit.
4. Run the overdue cron twice; confirm nothing double-charges.
5. Log in as the demo sales agent; confirm the other agent's contracts are invisible.
6. Print the Arabic contract PDF and read it.
7. Re-run the unit import; confirm counts are unchanged.
8. Full test suite green; every `US-xx` has at least one test naming it.

---

## Risks

- **Attribution.** The assistant writes most of the code, so the explain-back gates are not optional.
- **Scope creep.** Ch.7 exists so good ideas have somewhere to go that isn't v1.
- **Arabic RTL in QWeb** is the most likely thing to eat a session — wkhtmltopdf renders Arabic as
  disconnected letters if the font is missing. It's late (Story 08) on purpose; if it fights us, the
  English PDF ships and Arabic becomes a follow-up.
- **Security bolted on late** would mean stories 02–05 built and tested as admin, then broken when
  ACLs arrive. ACLs land in Story 02; only record rules wait for 06.
- **Cross-platform development.** Everything that matters lives in git: push at the end of every
  session; `.gitattributes` forces `eol=lf` so Windows never rewrites line endings; on Windows the
  project runs under **WSL2 (Ubuntu)**, so every command here works unchanged. `odoo-src/`, `venv/`,
  the database and `odoo.conf` are rebuilt, never copied.

---

## Stage 0 steps

No code, no Odoo install, no repo push.

1. Create `odoo-real-estate-eg/` with only `docs/` and `.squad/`.
2. Keep this plan in the repo as `docs/project-plan.md`.
3. Verify the domain facts (post-dated cheques, typical down payment and tenor, maintenance deposit
   %, late-fee practice) from sources, and cite them in the document.
4. Write `docs/business-requirements.md` in dependency order: Ch.2 → Ch.3 → Ch.4 → Ch.5 → Ch.6,
   then **Ch.1 last** (it is built from the others), then Ch.7 and Ch.8.
5. **Checkpoint 1:** Ch.1 is signed off and the Ch.8 open questions are answered. *(Done 2026-11-21.)*
6. After sign-off: the ten `intake.md` files and `00-overview.md` (they quote US/BR ids, so they wait
   until Ch.1 is final). **Checkpoint 2:** the stories are approved.
