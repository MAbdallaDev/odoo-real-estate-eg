#!/bin/sh
# S10.4: every user story US-xx in the business document has at least one test
# naming it (in a test name or docstring). Run by pre-commit, so by `make lint` and CI.
# Usage: scripts/check_us_tests.sh
set -u

spec="docs/business-requirements.md"
# v1.1: the tests of every addon in the repository (US-15 is in real_estate_eg_portal)
tests="addons"

ids=$(grep -oE '^#### US-[0-9]+' "$spec" | sed 's/^#### //' | sort -u)
if [ -z "$ids" ]; then
    echo "check_us_tests: FAIL - no '#### US-xx' heading found in $spec" >&2
    exit 1
fi

status=0
count=0
for id in $ids; do
    count=$((count + 1))
    if ! grep -rqw --include="test_*.py" -- "$id" "$tests"; then
        echo "check_us_tests: FAIL - no test names $id" >&2
        status=1
    fi
done

if [ "$status" -eq 0 ]; then
    echo "check_us_tests: OK - all $count user stories have a test naming them"
fi
exit "$status"
