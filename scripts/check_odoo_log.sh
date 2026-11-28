#!/bin/sh
# Fail an Odoo test run whose log is not clean.
# Usage: scripts/check_odoo_log.sh <logfile> [--no-tests]
#   - any WARNING, ERROR or CRITICAL line fails the run (S01.1: clean install log);
#   - no line from real_estate_eg's tests fails the run (guards against "0 tests, green"),
#     unless --no-tests is given (an install without tests, e.g. `make demo`).
set -u

log="${1:-}"
no_tests="${2:-}"
if [ ! -f "$log" ]; then
    echo "check_odoo_log: log file not found: '$log'" >&2
    exit 2
fi

status=0

if grep -E ' (WARNING|ERROR|CRITICAL) ' "$log"; then
    echo "check_odoo_log: FAIL - WARNING/ERROR/CRITICAL lines above" >&2
    status=1
fi

if [ "$no_tests" != "--no-tests" ] && ! grep -q 'odoo\.addons\.real_estate_eg\.tests\.' "$log"; then
    echo "check_odoo_log: FAIL - no real_estate_eg test ran" >&2
    status=1
fi

# v1.1: the customer portal API addon's tests too, when it was installed.
if [ "$no_tests" != "--no-tests" ] && grep -q 'real_estate_eg_portal' "$log" \
    && ! grep -q 'odoo\.addons\.real_estate_eg_portal\.tests\.' "$log"; then
    echo "check_odoo_log: FAIL - no real_estate_eg_portal test ran" >&2
    status=1
fi

if [ "$status" -eq 0 ]; then
    if [ "$no_tests" = "--no-tests" ]; then
        echo "check_odoo_log: OK - clean log"
    else
        echo "check_odoo_log: OK - clean log, real_estate_eg tests ran"
    fi
fi
exit "$status"
