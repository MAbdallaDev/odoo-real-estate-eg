# Developer shortcuts. GNU make on Linux or WSL2; run from the repo root.
# bash + pipefail so `odoo ... | tee log` still fails when Odoo fails.
SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -ec

PYTHON   := venv/bin/python
ODOO_BIN := $(PYTHON) odoo-src/odoo/odoo-bin
ODOO     := $(ODOO_BIN) -c odoo.conf
MODULE   := real_estate_eg
DB       ?= re_dev
TEST_DB  ?= re_test
TEST_LOG := odoo-test.log
DEMO_DB  ?= re_demo
DEMO_LOG := odoo-demo.log
ARGS     ?=
CI_COMPOSE := docker compose -f docker/docker-compose.ci.yml
CI_LOG   := odoo-ci.log
# Postgres role from odoo.conf, so dropdb connects as the same user as Odoo
DB_USER   = $(shell sed -n 's/^db_user *= *//p' odoo.conf)

.PHONY: help setup run test test-ci demo coverage shell lint release-apps

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

setup: ## Clone Odoo 19, create venv, install requirements, create odoo.conf
	[ -d odoo-src/odoo ] || git clone --depth 1 --branch 19.0 https://github.com/odoo/odoo.git odoo-src/odoo
	[ -d venv ] || python3 -m venv venv
	venv/bin/pip install -r odoo-src/odoo/requirements.txt -r requirements-dev.txt
	[ -f odoo.conf ] || { cp odoo.conf.example odoo.conf; chmod 600 odoo.conf; echo "odoo.conf created: set admin_passwd in it"; }
	venv/bin/pre-commit install

run: ## Start Odoo on database $(DB) (extra options: ARGS="...")
	$(ODOO) -d $(DB) $(ARGS)

test: ## Fresh $(TEST_DB), install the module, run its tests, check the log
	dropdb -U $(DB_USER) --if-exists --force $(TEST_DB)
	@echo "Installing $(MODULE) in a fresh $(TEST_DB) and running its tests (full log: $(TEST_LOG)) ..."
	@status=0; $(ODOO) -d $(TEST_DB) -i $(MODULE) --test-tags /$(MODULE) --stop-after-init $(ARGS) > $(TEST_LOG) 2>&1 || status=$$?; \
	grep -E 'odoo\.tests\.result|post-tests in' $(TEST_LOG) | tail -n 2 || true; \
	scripts/check_odoo_log.sh $(TEST_LOG) && exit $$status

demo: ## Fresh $(DEMO_DB) with demo data (Nile Heights), then check the install log
	dropdb -U $(DB_USER) --if-exists --force $(DEMO_DB)
	@echo "Installing $(MODULE) with demo data in a fresh $(DEMO_DB) (full log: $(DEMO_LOG)) ..."
	@status=0; $(ODOO) -d $(DEMO_DB) -i $(MODULE) --with-demo --stop-after-init $(ARGS) > $(DEMO_LOG) 2>&1 || status=$$?; \
	scripts/check_odoo_log.sh $(DEMO_LOG) --no-tests && exit $$status

coverage: ## Same as make test, measured by coverage.py (.coveragerc); prints the module's coverage
	dropdb -U $(DB_USER) --if-exists --force $(TEST_DB)
	@echo "Running the tests under coverage (full log: $(TEST_LOG)) ..."
	@status=0; venv/bin/coverage run odoo-src/odoo/odoo-bin -c odoo.conf -d $(TEST_DB) -i $(MODULE) --test-tags /$(MODULE) --stop-after-init $(ARGS) > $(TEST_LOG) 2>&1 || status=$$?; \
	grep -E 'odoo\.tests\.result' $(TEST_LOG) | tail -n 1 || true; \
	scripts/check_odoo_log.sh $(TEST_LOG) && venv/bin/coverage report && exit $$status

test-ci: ## Same test run as GitHub CI: Postgres + official Odoo 19 image in Docker
	@echo "Running the tests in Docker (full log: $(CI_LOG)) ..."
	@status=0; $(CI_COMPOSE) run --build --rm odoo > $(CI_LOG) 2>&1 || status=$$?; \
	$(CI_COMPOSE) down -v --remove-orphans > /dev/null 2>&1 || true; \
	grep -E 'odoo\.tests\.result|post-tests in' $(CI_LOG) | tail -n 2 || true; \
	scripts/check_odoo_log.sh $(CI_LOG) && exit $$status

# "shell" is an odoo-bin subcommand: it must come before -c, so $(ODOO) is not used here.
shell: ## Odoo Python shell on database $(DB)
	$(ODOO_BIN) shell -c odoo.conf -d $(DB) $(ARGS)

lint: ## Run every pre-commit check on all files
	venv/bin/pre-commit run --all-files

release-apps: ## Rebuild and push the 19.0 branch the Odoo Apps store reads (DRY_RUN=1 to only build)
	scripts/release_apps.sh
