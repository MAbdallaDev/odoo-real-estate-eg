# 01 — Environment and module skeleton

- **Feature:** `installments`
- **Intake:** `.squad/stories/installments/01-env-skeleton/intake.md`
- **Branch:** `story/01-env-skeleton`
- **Status:** awaiting maintainer approval of the Done Criteria

---

## Prerequisites

Checked on the development machine before this plan was written:

| Need | State |
|---|---|
| OS | Ubuntu 24.04 (Windows contributors use WSL2 Ubuntu; same commands) |
| Python | 3.12 with `python3-venv` and `python3-dev` |
| Build headers for Odoo's requirements | `build-essential`, `libpq-dev`, `libldap2-dev`, `libsasl2-dev` installed |
| PostgreSQL | 16, service active; local socket connections require a password |
| wkhtmltopdf | 0.12.6.1 (with patched Qt) |
| Docker | installed (used to reproduce CI locally, never for daily development) |
| `gh` CLI | installed, **not yet authenticated** |
| `git` | installed, global identity set |

Still to do, **by the maintainer** (these touch system accounts or credentials, so the assistant does
not run them):

1. **Postgres role.** Create a dedicated, non-superuser role with `CREATEDB` (Odoo refuses to run as
   `postgres`). Suggested name `odoo19_real_estate`:
   `sudo -u postgres createuser --createdb --pwprompt odoo19_real_estate`
2. **Password file.** Put the role's password in `~/.pgpass` (mode `600`), e.g. one line
   `localhost:5432:*:odoo19_real_estate:<password>` (libpq matches a `localhost` entry for Unix-socket
   connections too, so one line covers both). Then neither `odoo.conf` nor the Makefile holds a password, and `dropdb` works too.
3. **GitHub login.** `gh auth login` (the keyring can time out on this machine; if it does,
   `gh auth login --insecure-storage` stores the token in `~/.config/gh/hosts.yml` instead — the
   maintainer's call).
4. **Approval** to create the GitHub repository as **public**, and later to apply the `main` branch
   ruleset (both are asked for at the time, not assumed from this plan).

## Story Goal

Every later story lands on a working base: Odoo 19 Community runs from source on this machine with
this repo's `addons/` on its addons path; an empty `real_estate_eg` addon installs cleanly; `make run`,
`make test` and `pre-commit run --all-files` work; GitHub Actions runs the same lint and tests in
Docker against Postgres on every push and pull request; and the repository is public with `main`
protected so it changes only through reviewed pull requests.

No model, view, business rule or demo data is part of this story.

## Context — Read These Files First

**In the repo now:**

- `.squad/stories/installments/01-env-skeleton/intake.md` — S01.1–S01.7 and the technical hints.
- `docs/project-plan.md` — sections *Decisions made*, *Method*, *How we work, per stage*,
  *Target layout*, the Story 01 row, *Verification* and *Risks* (cross-platform bullet).
- `.squad/plans/installments/00-overview.md` — story order; Story 08 later adds an Arabic font to the
  CI image built here.

**Created by Task 2 (the Odoo clone), read before any file that depends on them is written.** Each
one is opened and the named symbol confirmed; if a name differs in 19.0, this plan is corrected in
the same commit as the code and the difference is logged in `docs/learning-log.md`.

- `odoo-src/odoo/setup.py` — supported Python versions.
- `odoo-src/odoo/requirements.txt` — dependency pins per Python version.
- `odoo-src/odoo/odoo/tools/config.py` — exact option names used by `odoo.conf.example` and the
  Makefile: `addons_path`, `db_user`, `db_host`, `test_tags`, `with_demo`, `http_port`,
  `log_level`. Already read on the upstream `19.0` branch while writing this plan: demo data is
  **off by default** (`--with-demo` / `with_demo`, default `False`), and setting `--test-tags`
  turns `test_enable` on by itself. Re-checked at the cloned commit.
- `odoo-src/odoo/odoo/service/server.py` — `preload_registries` adds 1 to the return code when the
  test report is not successful (read upstream while writing this plan), so a failing test already
  makes `--stop-after-init` exit non-zero; the log check covers what the exit code does not.
- `odoo-src/odoo/odoo/tests/__init__.py` — that `TransactionCase` and `tagged` are importable from
  `odoo.tests`.
- The module that defines `TagsSelector` (located with `grep -rn "class TagsSelector"
  odoo-src/odoo/odoo/tests/`) — the `--test-tags` grammar, to confirm `/real_estate_eg` selects
  exactly this module's tests.
- `odoo-src/odoo/addons/account/__manifest__.py` — `account`'s own `depends`, to confirm
  `['account', 'mail']` pulls nothing unexpected.

**Upstream hook manifests, read at the pinned revision when `.pre-commit-config.yaml` is written:**

- `OCA/maintainer-tools` `.pre-commit-hooks.yaml` — hook id `oca-fix-manifest-website` (confirmed
  on `master` while writing this plan).
- `OCA/odoo-pre-commit-hooks` `.pre-commit-hooks.yaml` — hook ids `oca-checks-odoo-module` (checks
  `.csv`, `.xml` and `__manifest__.py`) and `oca-checks-po` (confirmed on `main`).
- `OCA/pylint-odoo` `.pre-commit-hooks.yaml` — hook id `pylint_odoo` (confirmed on `main`).
- `OCA/oca-addons-repo-template` `src/.pre-commit-config.yaml.jinja` — OCA's reference config: XML
  is formatted by a `repo: local` prettier hook with `@prettier/plugin-xml`; the pinned versions for
  the 19.0 branch of that template are copied, not guessed.
- `astral-sh/ruff-pre-commit` — hook ids `ruff` and `ruff-format`, read at the pinned tag.

## Implementation tasks

Order follows *How we work, per stage*: the plan is committed to `main` before any code.

**Task 1 — First commit on `main` (Stage 0 work + this plan).**
1. `git init -b main` in the repo root.
2. Extend `.gitignore` (keeps `docs/private/` and `*.ar.md`) with `odoo-src/`, `venv/`, `*.conf`,
   `__pycache__/`, `*.py[co]`, `.coverage`, `htmlcov/`, `*.log`, `.ruff_cache/`.
3. Privacy scan before the first commit: `git add -A`, then `git ls-files` must list no `*.ar.md` and
   nothing under `docs/private/`; `git grep -n -I -E -f docs/private/privacy-patterns.txt` must print nothing.
   That pattern list is created in this task, inside the gitignored `docs/private/`, and reviewed by the
   maintainer (employer, home path, career details; the maintainer's own name is allowed as author).
4. Commit `docs/`, `.squad/`, `.gitignore`.

**Task 2 — Odoo 19 source and virtual environment.**
1. `git clone --depth 1 --branch 19.0 https://github.com/odoo/odoo.git odoo-src/odoo`; record
   `git -C odoo-src/odoo rev-parse HEAD` for the design note.
2. Read the *Created by Task 2* files above and confirm each symbol.
3. `python3 -m venv venv`; `venv/bin/pip install -r odoo-src/odoo/requirements.txt
   -r requirements-dev.txt`.
4. `requirements-dev.txt` (new): `pre-commit`, `coverage`, with versions pinned.

**Task 3 — GitHub repository (maintainer approval required).**
1. The maintainer runs `gh auth login`.
2. Ask, then `gh repo create odoo-real-estate-eg --public --source . --push` (description and
   topics impersonal).
3. `git switch -c story/01-env-skeleton`.

**Task 4 — Repo-level files.**
1. `.gitattributes`: `* text=auto eol=lf`, plus `*.png binary`, `*.pdf binary`.
2. `odoo.conf.example` (committed): `addons_path = odoo-src/odoo/addons,addons`,
   `db_user = odoo19_real_estate`, `admin_passwd` as an obvious placeholder, `http_interface = 127.0.0.1`
   (19.0 warns when it is unset), `http_port = 8019`,
   `with_demo = False` (explicit, though it is already the 19.0 default). `db_host`, `db_port` and
   `db_password` are left out: in 19.0 `False` for a non-boolean option logs a warning and is
   skipped (`config.py`, config-file parsing), and the defaults already mean "local socket, password
   from `~/.pgpass`". Option names exactly as read in `config.py`.
3. `odoo.conf` (local, gitignored): copied from the example by `make setup`; never committed.
4. `LICENSE`: the GNU LGPL v3 text, unmodified, from gnu.org.

**Task 5 — Addon skeleton** under `addons/real_estate_eg/`:
1. `__manifest__.py`: `name`, `summary`, `version` `19.0.1.0.0`, `category`, `license` `LGPL-3`,
   `author` (impersonal — see the approval question), `website` (the GitHub repo URL),
   `depends` `['account', 'mail']`, `data` `[]`, `installable` `True`, `application` `True` (so it is
   listed under Apps' default filter).
2. `__init__.py` (empty for now — no models yet).
3. `tests/__init__.py` importing `test_smoke`.
4. `tests/test_smoke.py`: `TestSmoke(TransactionCase)` tagged `post_install`, `-at_install`, with
   `test_module_installed` asserting `ir.module.module` for `real_estate_eg` has state `installed`.

**Task 6 — Makefile and log check.**
1. `scripts/check_odoo_log.sh <logfile>`: exits non-zero if the log has any `ERROR` or `CRITICAL`
   line, any `WARNING` line, or no line showing that `real_estate_eg` tests ran (exact log wording
   taken from a real run, not guessed). Plain POSIX `sh` + `grep`, no GNU-only flags.
2. `Makefile` (GNU make, Linux/WSL2; no macOS-only flags such as `sed -i ''`). Variables
   `ODOO = venv/bin/python odoo-src/odoo/odoo-bin -c odoo.conf`, `DB ?= re_dev`,
   `TEST_DB ?= re_test`. Targets:
   - `setup` — clone (if missing), venv, requirements, `odoo.conf` from the example (if missing),
     `pre-commit install`.
   - `run` — `$(ODOO) -d $(DB)`.
   - `test` — `dropdb --if-exists --force $(TEST_DB)`, then
     `$(ODOO) -d $(TEST_DB) -i real_estate_eg --test-tags /real_estate_eg --stop-after-init`
     (the intake's `--test-enable` is implied by `--test-tags` in 19.0) piped through `tee` to a log file, preserving Odoo's exit code, then
     `scripts/check_odoo_log.sh` on that log.
   - `shell` — `$(ODOO) shell -d $(DB)`.
   - `lint` — `pre-commit run --all-files`.

**Task 7 — Pre-commit (OCA stack).**
1. `.pre-commit-config.yaml` with pinned revs: `pre-commit-hooks` basics (trailing whitespace,
   end-of-file, merge conflicts, YAML check), `ruff` + `ruff-format`, `pylint_odoo`,
   `oca-checks-odoo-module`, `oca-fix-manifest-website`, prettier with `@prettier/plugin-xml` for XML.
   `odoo-src/`, `venv/` and `docs/private/` are excluded.
2. Config files the hooks read: `.ruff.toml`, `.pylintrc` (`load-plugins=pylint_odoo`,
   `valid-odoo-versions=19.0`, the manifest author setting), `prettier.config.cjs` (OCA's form: `require.resolve` finds the XML plugin in pre-commit's Node env; a `.prettierrc.yml` plugin entry cannot).
3. `pre-commit run --all-files` green.

**Task 8 — CI in Docker.**
1. `docker/docker-compose.ci.yml`: service `db` (`postgres:16`, user/password `odoo`, a health
   check) and service `odoo` (the official `odoo:19.0` image — it ships wkhtmltopdf with patched Qt —
   pinned by digest, `../addons` mounted read-only on its extra-addons path, `depends_on` db healthy).
2. `.github/workflows/ci.yml`, on `push` and `pull_request`:
   - job `pre-commit`: checkout, Python 3.12, `pip install pre-commit`, `pre-commit run --all-files
     --show-diff-on-failure`, with the pre-commit cache keyed on the config file;
   - job `test`: `docker compose -f docker/docker-compose.ci.yml run --rm odoo` with the same Odoo
     test arguments as `make test`, log captured, then `scripts/check_odoo_log.sh` on it.
3. `docker compose ... run` reproduced locally once before pushing.

**Task 9 — Docs.**
1. `README.md`: what the module does (installment sales and collections for Egyptian real-estate
   developers), status (skeleton), requirements, install and run (`make setup`, `make run`), tests
   and quality gates, the AI-assistance disclosure (built with AI assistance, every line reviewed by
   the maintainer, mistakes caught logged in `docs/learning-log.md`), licence. Impersonal; no local
   paths.
2. `docs/learning-log.md`: two sections — *Explain-back answers* (one heading per story) and
   *AI mistakes caught in review* (date, story, what was wrong, how it was caught, fix).
3. `docs/design-notes/01-environment.md`: how Odoo runs from source, addons path, `odoo.conf`,
   manifest, how tests are selected and run, what pre-commit and CI check, the pinned Odoo commit and
   image digest, the negative checks from the Test Plan, alternatives considered (Docker for
   development, OCA's CI images); ends with 3 explain-back questions.

**Task 10 — Pull request and `main` protection.**
1. Push the branch, open the PR: links this plan, ticks the Done Criteria, CI green.
2. After the first CI run (so its check names exist), ask, then apply a ruleset on `main`: pull
   request required (0 approvals — solo maintainer), status checks `pre-commit` and `test` required,
   no bypass, force-push and deletion blocked.
3. The maintainer reviews and merges. CI runs on `main` after the merge and must be green.
4. The maintainer answers the three questions in `docs/learning-log.md` (through a PR).

## Edge Cases & Failure Modes

1. **Tests of every installed module run.** `-i real_estate_eg --test-enable` alone also runs the
   at-install tests of `account`, `mail` and their dependencies on a fresh database — tens of minutes.
   `--test-tags /real_estate_eg` restricts the run to this module.
2. **Green with zero tests.** If `tests/__init__.py` does not import `test_smoke`, Odoo runs nothing
   and still exits 0. `check_odoo_log.sh` fails when no `real_estate_eg` test ran.
3. **Exit code 0 despite errors.** A failing test changes the exit code, but an error logged
   outside a test (for example while loading a data file) may not. The log check fails on any
   `ERROR`/`CRITICAL`.
4. **Warnings that are not ours.** S01.1 asks for no warning in the log. If core emits an unavoidable
   warning, it is not silenced in the check script without the maintainer's agreement; the exact line
   and the reason go in the design note.
5. **Stale test database.** Re-running `make test` against an existing `re_test` would update rather
   than install. `dropdb --if-exists --force` gives a fresh database every run; `make run` uses a
   different database so the two never collide.
6. **Odoo run as `postgres`.** Refused by Odoo; the dedicated `odoo19_real_estate` role avoids it.
7. **Password prompts.** Local Postgres requires a password; `~/.pgpass` serves both Odoo (libpq) and
   `dropdb`. If it is missing or not mode `600`, connection fails — the design note says how to tell.
8. **Python / wheel mismatch.** If a pin in `requirements.txt` has no wheel for Python 3.12 it builds
   from source; the headers listed in Prerequisites cover `psycopg2` and `python-ldap`.
9. **wkhtmltopdf missing** makes Odoo log a warning, which would fail the log check. Installed locally;
   the official image ships it.
10. **Local vs CI drift.** Local runs `19.0` at the cloned commit, CI runs the image's build. Both
    are pinned (commit hash, image digest) and recorded in the design note; a test that passes
    locally and fails in CI is investigated, not retried.
11. **`*.conf` ignores too much.** Any config CI needs is passed as environment or command-line
    arguments, or named `*.example`; `git check-ignore -v` confirms `odoo.conf.example` is tracked.
12. **CRLF from Windows editors** — `.gitattributes` normalises to LF.
13. **Hook drift.** Every pre-commit rev is pinned; `pre-commit autoupdate` only in a deliberate
    commit. The prettier hook fetches Node through pre-commit; the first run is slow.
14. **pylint-odoo defaults expect an OCA author** — set in `.pylintrc`, not by adding OCA as author.
15. **Port 8019 busy** — `make run` passes extra arguments through (`make run ARGS="--http-port 8029"`).
16. **Branch protection order.** A required status check can only be selected after it has run once,
    and protection applied before the Stage 0 push would block it — hence Task 10's order.
17. **Private data in a public repo.** Push history cannot be fully recalled. The Task 1 scan runs
    before the first push, and again on the PR diff.
18. **`gh` keyring timeout** — the maintainer chooses `--insecure-storage` or retries; the assistant
    never handles the token.

## Test Plan

| # | Test | Proves |
|---|---|---|
| T1 | `addons/real_estate_eg/tests/test_smoke.py` — `TestSmoke.test_module_installed` | S01.2: the runner finds and runs this module's tests |
| T2 | `make test` exit code and `scripts/check_odoo_log.sh` result | S01.1 (clean install log), S01.2 |
| T3 | CI jobs `pre-commit` and `test` on the PR and on `main` after merge | S01.3, S01.4 |

**Negative checks** — each gate must be seen failing once, then restored; results go in the design
note:

- N1: change T1's expected state to `uninstalled` → `make test` exits non-zero.
- N2: remove the import from `tests/__init__.py` → `make test` fails with "no tests ran".
- N3: set the manifest `version` to `1.0` → `pre-commit run --all-files` fails on a pylint-odoo check.
- N4: add a stray `_logger.warning(...)` at import time in `__init__.py` → the log check fails.

None of N1–N4 is committed.

## Verification Steps

```bash
make setup                       # clone, venv, requirements, odoo.conf, pre-commit install
make test                        # fresh re_test, T1 runs, log clean, exit 0
make lint                        # pre-commit run --all-files, green
make run                         # http://localhost:8019 → Apps → install real_estate_eg; log clean
git check-ignore -v odoo.conf venv odoo-src docs/private docs/project-plan.ar.md   # all ignored
git ls-files odoo.conf.example .gitattributes LICENSE                         # all tracked
docker compose -f docker/docker-compose.ci.yml run --rm odoo ...              # CI test job, locally
gh run list --branch main --limit 1                                           # CI green on main
gh api repos/{owner}/{repo}/rulesets                                          # main ruleset present
```

## Done Criteria

- [ ] **S01.1** `make run` starts Odoo 19 from `odoo-src/odoo` with `addons/` on the addons path, and
  `real_estate_eg` installs from Apps with no error or warning in the log. *Proof:* manual install on
  `re_dev`, log excerpt in the PR; T2 checks the same install log automatically.
- [ ] **S01.2** `make test` installs `real_estate_eg` in a fresh database with tests enabled and exits
  0; one smoke test proves the test runner finds the module's tests. *Proof:* T1 + T2; N1 and N2 show
  the gate fails when it should.
- [ ] **S01.3** `pre-commit run --all-files` passes with the OCA stack (`ruff`, `pylint-odoo`,
  `oca-fix-manifest-website`, XML and CSV checks). *Proof:* `make lint` green; N3 fails it.
- [ ] **S01.4** CI runs pre-commit and the test suite in Docker against Postgres on every push and
  pull request, and is green on `main`. *Proof:* T3 — run links in the PR and the post-merge run on
  `main`.
- [ ] **S01.5** `.gitignore` excludes `odoo-src/`, `venv/`, `*.conf`, `docs/private/` and `*.ar.md`;
  `.gitattributes` sets `* text=auto eol=lf`; `odoo.conf.example` is committed, `odoo.conf` is not.
  *Proof:* the `git check-ignore` / `git ls-files` lines in Verification Steps.
- [ ] **S01.6** `README.md` states what the module does, how to install and run it, and that it was
  built with AI assistance with every line reviewed; `LICENSE` is LGPL-3; `docs/learning-log.md`
  exists. *Proof:* files in the PR diff, reviewed by the maintainer.
- [ ] **S01.7** The repo is public on GitHub and `main` changes only through pull requests. *Proof:*
  `gh repo view --json visibility` shows `PUBLIC`; the ruleset from Task 10 is listed; a direct push
  to `main` is rejected.
