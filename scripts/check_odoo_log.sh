#!/bin/sh
# Fail an Odoo test run whose log is not clean.
# Usage: scripts/check_odoo_log.sh <logfile>
#   - any WARNING, ERROR or CRITICAL line fails the run (S01.1: clean install log);
#   - no line from real_estate_eg's tests fails the run (guards against "0 tests, green").
set -u

log="${1:-}"
if [ ! -f "$log" ]; then
    echo "check_odoo_log: log file not found: '$log'" >&2
    exit 2
fi

status=0

if grep -E ' (WARNING|ERROR|CRITICAL) ' "$log"; then
    echo "check_odoo_log: FAIL - WARNING/ERROR/CRITICAL lines above" >&2
    status=1
fi

if ! grep -q 'odoo\.addons\.real_estate_eg\.tests\.' "$log"; then
    echo "check_odoo_log: FAIL - no real_estate_eg test ran" >&2
    status=1
fi

if [ "$status" -eq 0 ]; then
    echo "check_odoo_log: OK - clean log, real_estate_eg tests ran"
fi
exit "$status"
