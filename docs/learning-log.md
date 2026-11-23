# Learning log

Two records kept side by side:

1. **Explain-back answers** — each story's design note ends with three questions; the
   maintainer answers them here, in their own words, before the next story starts.
2. **Mistakes caught** — every time the AI assistant got something wrong and review, a
   test or a quality gate caught it. This is the evidence that the code is reviewed, not
   just generated.

---

## Explain-back answers

### Story 01 — Environment and module skeleton

Questions: [`design-notes/01-environment.md`](design-notes/01-environment.md#explain-back-questions)

1. Without dropping `re_test`, the old database stays: the module is already installed, so
   `-i` acts as an update, not a fresh install, and old data stays. A test could then pass or
   fail because of leftover data, and an error that only happens on a fresh install would be
   missed. Without `--test-tags /real_estate_eg`, Odoo would also run the tests of every module
   installed with ours (`account`, `mail` and their dependencies), so the run would take tens
   of minutes instead of seconds.
2. First, a warning or error in the log: Odoo still exits 0, like the missing `http_interface`
   warning on our first run. Second, zero tests ran: if `tests/__init__.py` does not import the
   test file, Odoo finds no test and still exits 0 (negative check N2).
   `scripts/check_odoo_log.sh` catches both: it fails on any `WARNING`/`ERROR`/`CRITICAL` line
   and when no `real_estate_eg` test ran.
3. From Docker images: `docker/docker-compose.ci.yml` starts two containers from ready-made
   images, `postgres:16` and the official `odoo:19.0`, and mounts our `addons/` folder into the
   Odoo container, so nothing has to be installed on the CI machine. The images are pinned by
   digest so the version never changes by itself: the `odoo:19.0` tag moves to new builds, so
   without the pin CI could fail one day with no change in our code. We update the digest on
   purpose, in a commit.

### Story 02 — Core models, views, states and access rights

Questions: [`design-notes/02-core-models.md`](design-notes/02-core-models.md#explain-back-questions)

*(to be answered)*

---

## Mistakes caught

| Date | Story | What was wrong | How it was caught | Fix |
|---|---|---|---|---|
| 2026-11-22 | 01 | The plan wrote `db_host = False`, `db_port = False` and `db_password = False` in `odoo.conf.example`. In Odoo 19 a `False` value for a non-boolean option logs a `WARNING` and is skipped, which breaks the "no warning in the log" rule. | Reading Odoo 19's config-file parser (`odoo/tools/config.py`) before writing the file | Lines left out; the defaults already mean "local socket, password from `~/.pgpass`" |
| 2026-11-22 | 01 | `http_interface` was not set. Odoo 19 warns that the default `0.0.0.0` (listen on every network) changes to `127.0.0.1` in Odoo 20. | The `make test` log check failed on the first run | `http_interface = 127.0.0.1` in `odoo.conf.example`; CI passes `--http-interface` |
| 2026-11-22 | 01 | The prettier XML plugin was declared in `.prettierrc.yml`, where prettier 3 cannot load it from pre-commit's own Node environment. | `make lint` failed: `Cannot find package '@prettier/plugin-xml'` | Replaced by `prettier.config.cjs` with `require.resolve(...)`, as OCA's template does |
| 2026-11-22 | 01 | A negative check (test import commented out on purpose) was staged and committed before being undone, so the committed module ran no test. | Reviewing the commit before pushing: `git show HEAD:addons/real_estate_eg/tests/__init__.py` | Undo, `make test`, then `git commit --amend` (not yet pushed). Rule: undo negative-check edits before `git add`. |
| 2026-11-23 | 02 | The delivery date was checked only when Deliver was clicked, so a future date typed on the form stayed stored on a contract that was then cancelled instead of delivered. | The maintainer's walk-through: the data showed a cancelled contract with a delivery date in the future | `@api.constrains` on `delivery_date`: checked on every save; the stored value was cleared |
| 2026-11-23 | 02 | The first read-only test (AC-06.3) only tried to edit a confirmed contract, which the Python edit guard already blocks, so it never tested the access rights. | Negative check N4: giving collections officers write rights did not make the test fail | A draft contract added to the test; N4 then failed on four points |
| 2026-11-23 | 02 | The "two contracts for one unit in the same save" test used a unit that already had a contract, so it passed for the wrong reason. | Re-reading the test before committing | A fresh unit, and the test checks the exact message |
| 2026-11-23 | 02 | Plan links to the business rules used `<a id>` anchors, which the review tool's file pane does not follow. | The maintainer clicked the links; a five-way link test showed only heading links work | Each id links to its heading (BR to its group, US and AC to their story), with the rule text as hover title |
| 2026-11-23 | 02 | Two scripted text replacements did not apply after the formatter had re-wrapped the lines, so a test run checked the old code. | Reading the file after the run, before committing | Edited by hand and re-run. Rule: after a scripted edit, check the diff before trusting a test run. |
