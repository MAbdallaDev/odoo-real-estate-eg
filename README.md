# Real Estate Installments (Egypt) — Odoo 19

[![CI](https://github.com/MAbdallaDev/odoo-real-estate-eg/actions/workflows/ci.yml/badge.svg)](https://github.com/MAbdallaDev/odoo-real-estate-eg/actions/workflows/ci.yml)
![Odoo 19.0](https://img.shields.io/badge/Odoo-19.0%20Community-714B67)
![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue)

`real_estate_eg` is an Odoo 19 Community addon for Egyptian real-estate developers who sell
units on installment plans and then have to collect them.

In Egypt a unit is rarely paid in cash: the buyer pays a down payment, then years of
quarterly or monthly installments, a maintenance deposit at delivery, and late fees on
anything overdue. Odoo has no concept of any of this, so every implementation partner
rebuilds it. This module does it once, on top of standard Odoo accounting.

> **Status: Story 02 of 10 — core models, states and access rights.** Projects, units and
> contracts with their screens; a contract moves draft → confirmed → delivered or is
> cancelled, a unit can never be sold twice, and every role has its access rights, all
> tested as real users. Business features land one reviewed pull request at a time; see
> [Roadmap](#roadmap).

## What v1 will do

- **Contracts** for project units, moving through draft → confirmed → delivered → closed,
  or cancelled with the developer's retention computed.
- **Payment schedules** generated from plan templates: down payment, N installments
  (monthly or quarterly), the rounding difference on the last line, and the maintenance
  deposit as its own scheduled amount.
- **Invoicing through standard accounting:** each installment becomes a customer invoice on
  its due date, booked to customer advances; paid / outstanding amounts are read from real
  payments.
- **Collections:** overdue lines flagged nightly, late fees computed from payment history
  (re-running the job never double-charges), due-this-month and aging views.
- **Security:** sales agents see only their own contracts; multi-company aware.
- **Bilingual contract PDF**, Arabic and English side by side.
- **Unit import** from a spreadsheet, re-runnable without duplicates.

The full specification — business rules `BR-xx`, user stories `US-xx` with acceptance
criteria, and an invented developer, *Nile Heights Developments*, whose numbers become the
demo data and test fixtures — is in
[`docs/business-requirements.md`](docs/business-requirements.md).

## Requirements

- Linux, or Windows with **WSL2 (Ubuntu)** — every command below works unchanged there
- Python **3.12** (Odoo 19 supports 3.10+) with `python3-venv` and `python3-dev`
- PostgreSQL **16**, plus build headers for Odoo's requirements:
  `build-essential libpq-dev libldap2-dev libsasl2-dev`
- **wkhtmltopdf 0.12.6.1 with patched Qt** (for PDF reports)
- Docker (only to reproduce CI locally)

## Quick start

```bash
# 1. A Postgres role for Odoo: not a superuser, allowed to create databases
sudo -u postgres createuser --createdb --pwprompt odoo19_real_estate

# 2. Store its password in ~/.pgpass so neither Odoo nor dropdb asks for it
#    (read -s keeps the password off the screen and out of shell history)
read -rsp 'Password: ' P; echo; printf 'localhost:5432:*:odoo19_real_estate:%s\n' "$P" >> ~/.pgpass; unset P
chmod 600 ~/.pgpass

# 3. Clone, then build everything: Odoo 19 source, venv, requirements, odoo.conf, git hook
git clone https://github.com/MAbdallaDev/odoo-real-estate-eg.git
cd odoo-real-estate-eg
make setup          # then set admin_passwd in odoo.conf

# 4. Run
make run            # http://localhost:8019 → Apps → "Real Estate Installments (Egypt)"
```

`make setup` clones Odoo 19 Community into `odoo-src/` and creates `venv/`; both are
gitignored and rebuilt, never copied. `odoo.conf` is created from
[`odoo.conf.example`](odoo.conf.example) and is gitignored too.

## Daily commands

| Command | What it does |
|---|---|
| `make run` | Odoo on database `re_dev`, port 8019 (`ARGS="..."` passes extra options) |
| `make test` | Fresh `re_test` database, installs the module, runs its tests, checks the log |
| `make test-ci` | The same test run inside Docker, exactly as CI runs it |
| `make lint` | Every pre-commit check on all files |
| `make shell` | Odoo Python shell on `re_dev` |
| `make help` | List the targets |

## Quality gates

- **Tests** — `make test` fails if a test fails, if the log contains any `WARNING`, `ERROR`
  or `CRITICAL` line, or if no test of this module ran at all
  ([`scripts/check_odoo_log.sh`](scripts/check_odoo_log.sh)).
- **Lint** — the OCA pre-commit stack, pinned to the versions OCA uses for Odoo 19: `ruff`,
  `pylint-odoo` (OCA's mandatory checks), `oca-checks-odoo-module`,
  `oca-fix-manifest-website`, `prettier` with the XML plugin, and basic file checks. It runs
  on every commit.
- **CI** — GitHub Actions runs the lint and the tests (Postgres 16 + the official Odoo 19
  image, both pinned by digest) on every push and pull request. `main` changes only through
  pull requests with green CI.

## Roadmap

| # | Story | Status |
|---|---|---|
| 01 | Environment and module skeleton | done |
| 02 | Core models, views, states and access rights | in review |
| 03 | Payment plan templates and the schedule generator | planned |
| 04 | Accounting link: invoices, payment state, closing and cancellation money | planned |
| 05 | Overdue lines, late fees and the at-risk flag | planned |
| 06 | Record rules: agents see their own contracts; multi-company | planned |
| 07 | Collections screens and query performance | planned |
| 08 | Bilingual Arabic / English contract PDF | planned |
| 09 | Post-dated cheques (stretch) | planned |
| 10 | Ship v1.0.0: unit import, demo data | planned |

## How this is built

Each story has a written intake and plan in [`.squad/`](.squad/) whose Done Criteria
become the tests, one branch and one pull request per story, and a design note in
[`docs/design-notes/`](docs/design-notes/) explaining why it is built that way.

**Built with AI assistance.** Every story starts from a written spec and plan; an AI
coding assistant helps implement it, and every change is reviewed and merged by the
maintainer. Mistakes caught in review are logged in
[`docs/learning-log.md`](docs/learning-log.md), with the maintainer's own explanation of
each story.

## License

[LGPL-3](LICENSE), the same license as Odoo Community addons.
