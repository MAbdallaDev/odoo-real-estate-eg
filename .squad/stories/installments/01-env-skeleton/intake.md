# Story intake — 01-env-skeleton

> **Source:** manual entry (no tracker). Rules, user stories and acceptance criteria below are pasted
> verbatim from `docs/business-requirements.md` v0.2 — if they ever disagree, that document wins.

---

## Feature

- **Feature name (display):** Real estate installments & collections
- **Feature slug (folder under `plans/`):** `installments`

## Tracker (metadata only)

- **Tracker type:** `none`
- **Work item id:** `01-env-skeleton`

---

## Title

Environment and module skeleton

---

## Description

Set up everything the next nine stories stand on: an Odoo 19 Community source checkout, a Python
virtual environment, a local Postgres role and database, and an empty `real_estate_eg` addon that
installs cleanly. Add the quality gates from day one — the OCA pre-commit stack and a GitHub Actions
CI that runs the linters and the test suite in Docker against Postgres — so every later story lands
through a green pipeline.

The repo goes public in this story, so the repo-level files (README with the AI-assistance
disclosure, LGPL-3 LICENSE, `.gitignore`, `.gitattributes`, `odoo.conf.example`) are written here.

---

## Acceptance criteria

### Story-level criteria

- **S01.1** `make run` starts Odoo 19 from `odoo-src/odoo` with this repo's `addons/` on the addons
  path, and `real_estate_eg` installs from Apps with no error or warning in the log.
- **S01.2** `make test` installs `real_estate_eg` in a fresh database with tests enabled and exits 0;
  one smoke test proves the test runner finds the module's tests.
- **S01.3** `pre-commit run --all-files` passes with the OCA stack (`ruff`, `pylint-odoo`,
  `oca-fix-manifest`, XML and CSV formatters).
- **S01.4** CI runs pre-commit and the test suite in Docker against Postgres on every push and pull
  request, and is green on `main`.
- **S01.5** `.gitignore` excludes `odoo-src/`, `venv/`, `*.conf`, `docs/private/` and `*.ar.md`;
  `.gitattributes` sets `* text=auto eol=lf`; `odoo.conf.example` is committed, `odoo.conf` is not.
- **S01.6** `README.md` states what the module does, how to install and run it, and that it was built
  with AI assistance with every line reviewed; `LICENSE` is LGPL-3; `docs/learning-log.md` exists.
- **S01.7** The repo is public on GitHub and `main` changes only through pull requests.

---

## Attachments

None. Everything the planner needs is pasted above.

---

## Dependencies

- **Blocked by / related ids:** none
- **Depends on code areas or other stories:** none — first story.

## Extra notes (optional)

This story has no user story behind it; its criteria are the project plan's Story 01 row.

## Technical hints (optional)

Names below are hints. Each one is verified in `odoo-src/` before the plan cites it (no invented symbols).

- Odoo 19 Community, shallow clone of the `19.0` branch into `odoo-src/odoo` (gitignored).
- Python venv in `venv/`; install Odoo's `requirements.txt` plus `requirements-dev.txt` (pre-commit, coverage).
- Manifest: `license` `LGPL-3`, version `19.0.1.0.0`, `depends` `['account', 'mail']`.
- Makefile targets: `run`, `test`, `shell`. Test command shape: `odoo -d <db> -i real_estate_eg --test-enable --stop-after-init`.
- CI image needs wkhtmltopdf (patched Qt) for later PDF tests; an Arabic font is added in Story 08.
- Windows users run everything inside WSL2 (Ubuntu); nothing in the Makefile may assume macOS.

## Out of scope

- Any model, view or business rule (Story 02 onwards).
- Demo data (Story 10).
- Odoo.sh or any hosted deployment.
