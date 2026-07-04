#!/usr/bin/env bash
# Run the whole claude_knows test suite.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
echo "== ck-route =="; python3 tests/test_ck_route.py || fail=1
echo; echo "== ck-usage =="; python3 tests/test_ck_usage.py || fail=1
echo
if [ "$fail" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit "$fail"
