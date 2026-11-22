# 01 — Environment and module skeleton

Plan: [`.squad/plans/installments/01-env-skeleton/plan.md`](../../.squad/plans/installments/01-env-skeleton/plan.md)

Story 01 builds no business feature. It builds the ground every later story stands on: Odoo 19
running from source, an empty `real_estate_eg` addon that installs cleanly, and three gates —
tests, lint, CI — that every later change has to pass.

## How Odoo runs here

**From source, not from a package.** `odoo-src/odoo` is a shallow clone of the `19.0` branch
(commit `d36b9405fe5d2ede753c6d7eceb778ecef20f67b` at the time of writing). It runs with the
Python in `venv/`, which holds Odoo's own `requirements.txt` and the dev tools. This is the usual
setup in Odoo partner shops and what Odoo.sh mirrors; a debugger can stop inside core code.

**One config file.** `odoo-bin -c odoo.conf` reads every option from `odoo.conf`, which is
gitignored and created from the committed `odoo.conf.example`. Relative paths resolve from the
current directory, so Odoo is always started from the repo root — the Makefile does that.

**Addons path.** `addons_path = odoo-src/odoo/addons,addons`: Odoo's own modules first, then this
repo's `addons/` folder. A folder is a module when it contains `__manifest__.py`.

**The database user.** Odoo connects as `odoo19_real_estate`, a role that can create databases
but is not a superuser. Odoo refuses to run as `postgres`, and a superuser could read or drop every
database on the machine. Its password lives in `~/.pgpass` (mode `600`), which libpq — and so both
Odoo and `dropdb` — reads by itself. `odoo.conf` holds no password, and the Unix socket is used
because `db_host` / `db_port` are left out.

**Databases are created by Odoo, never by hand.** `odoo-bin -d re_dev` creates the empty database
if it is missing, then fills it: tables, the `base` module, the admin user. `re_dev` is kept for
manual work; `re_test` is dropped and recreated by every `make test`.

**Two settings exist only to keep the log clean.** `http_interface = 127.0.0.1` (Odoo 19 warns when
it is unset, and it keeps the server off the network) and no `False` values for non-boolean options
(Odoo 19 warns and skips them). Demo data is off by default in Odoo 19 (`with_demo`); tests never
rely on it.

## The manifest

`__manifest__.py` is the module's ID card. The fields that matter now:

- `version: "19.0.1.0.0"` — the Odoo series, then the module's own version. pylint-odoo enforces
  the format `19.0.x.y.z`.
- `depends: ["account", "mail"]` — installing this module installs those first (49 modules in all).
  Story 04 needs accounting; Story 02 needs the chatter.
- `license: "LGPL-3"`, `author`, `website` (forced to the repo URL by `oca-fix-manifest-website`).
- `application: True` — the module is listed under the Apps menu's default filter.
- `data: []` — no XML or CSV yet; Story 02 adds views and access rights.

## How the tests run

```bash
odoo-bin -c odoo.conf -d re_test -i real_estate_eg --test-tags /real_estate_eg --stop-after-init
```

- `-i` installs the module (and its dependencies) into the fresh `re_test`.
- `--test-tags /real_estate_eg` runs **only this module's tests**. Without it, `--test-enable`
  would also run the at-install tests of `account`, `mail` and everything under them — tens of
  minutes instead of about 25 seconds. In Odoo 19 `--test-tags` turns test mode on by itself.
- `--stop-after-init` exits when done, so the run can be scripted.
- The smoke test is tagged `post_install`: it runs once every module is loaded, when the module's
  state is already `installed`.

**Why a log check on top of the exit code.** Odoo exits non-zero when a test fails, but two
failures stay invisible to the exit code: an error or warning logged outside a test, and a run where
no test was found at all (a missing import in `tests/__init__.py`). `scripts/check_odoo_log.sh`
fails on any `WARNING` / `ERROR` / `CRITICAL` line and when no `real_estate_eg` test ran.

## What the quality gates check

| Gate | Command | Catches |
|---|---|---|
| Tests | `make test` | failing tests, warnings or errors in the install log, "green with zero tests" |
| Lint | `make lint`, and on every commit | Odoo rules (pylint-odoo, OCA's mandatory list for 19.0), module XML/CSV/manifest (`oca-checks-odoo-module`), Python style and import order (`ruff`), XML/YAML formatting (`prettier`), whitespace and line endings |
| CI | every push and pull request | the same lint, and the same tests in Docker |

All hook versions are the ones OCA's addons-repo template pins for Odoo 19, so this repo is linted
the way an OCA reviewer would lint it.

**CI in Docker.** GitHub gives each job an empty Ubuntu machine. Instead of installing Postgres,
wkhtmltopdf and Odoo there on every run, `docker/docker-compose.ci.yml` starts two ready-made
images — `postgres:16` and the official `odoo:19.0` (build `19.0-20261112`, Python 3.12.3,
wkhtmltopdf 0.12.6.1 with patched Qt) — and mounts `addons/` read-only into Odoo's
`/mnt/extra-addons`. Both images are pinned by digest, so CI never changes version silently.
`make test-ci` runs the identical stack locally.

**Local and CI run slightly different Odoo builds** (the cloned commit vs. the image's nightly).
Both are recorded here; a test that passes locally and fails in CI is investigated, not retried.

## The gates were seen failing

A gate that has never failed proves nothing. Each was broken on purpose once, then restored
(none of these changes was committed):

| Check | Change | Result |
|---|---|---|
| N1 | smoke test expects `uninstalled` | `1 failed`, `make test` exit 2 |
| N2 | test import commented out | Odoo: `0 tests` (warning); log check: "no real_estate_eg test ran"; exit 2 |
| N3 | manifest version `1.0` | pylint-odoo `C8106 manifest-version-format`; `make lint` exit 2 |
| N4 | a stray warning in the log | covered by a real case: the missing `http_interface` warning failed the first `make test` |

## Known warning: cron during an install from the browser

Installing the module from the Apps screen of a running server logs, twice:

```
WARNING re_dev odoo.addons.base.models.ir_cron: Skipping database re_dev because of modules to install/upgrade/remove.
```

The scheduled-jobs thread woke up while the install was in progress and skipped that round. It comes
from Odoo core, only during an interactive install, and not from this module; the scripted install
in `make test` and CI has a clean log. It is documented here rather than silenced.

## Alternatives considered

- **Docker for daily development.** Rejected: slower edit-run loop, harder debugging inside core
  code, and further from how partner shops and Odoo.sh work. Docker is kept for CI only.
- **OCA's CI images** (`oca-ci`) and its copier template. They would bring the whole OCA toolchain
  in one step, but hide most of what this story is meant to teach. The pre-commit pins and
  pylint rules are taken from that template instead.
- **Odoo installed from a `.deb` or pip.** Rejected: no core source to read or step into.

## Explain-back questions

Answer in your own words in [`../learning-log.md`](../learning-log.md#story-01--environment-and-module-skeleton).

1. `make test` deletes `re_test` and lets Odoo create it again, and runs with
   `--test-tags /real_estate_eg`. What would go wrong without each of those two choices?
2. Odoo exited with code 0, yet `make test` failed. Name two situations where that is the right
   result, and what in this repo detects each one.
3. CI runs on a brand-new machine. How do the tests get a Postgres server and an Odoo 19 there,
   and why are the images pinned by digest instead of just `odoo:19.0`?
