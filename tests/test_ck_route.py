#!/usr/bin/env python3
"""Tests for the ck-route classifier. Run: python3 tests/test_ck_route.py"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
from ck_config import load_config  # noqa: E402

# Import bin/ck-route (hyphen, no .py) by file path via an explicit source loader.
from importlib.machinery import SourceFileLoader  # noqa: E402

_loader = SourceFileLoader("ck_route", os.path.join(ROOT, "bin", "ck-route"))
_spec = importlib.util.spec_from_loader("ck_route", _loader)
ck_route = importlib.util.module_from_spec(_spec)
_loader.exec_module(ck_route)

CFG = load_config()

# (prompt, expected_tier)
CASES = [
    ("fix the typo in the readme", "haiku"),
    ("what is a mutex", "haiku"),
    ("rename foo to bar", "haiku"),
    ("2+2?", "haiku"),
    ("add a login button to the settings page", "sonnet"),
    ("write a function that validates an email address", "sonnet"),
    ("update the docs for the new endpoint", "sonnet"),
    ("refactor the auth module across all services", "opus"),
    ("design the architecture for a distributed job queue", "opus"),
    ("debug why the app deadlocks under concurrency", "opus"),
    ("make a plan to migrate the database to postgres", "opus"),
]

failures = []
for prompt, expected in CASES:
    tier, reason, conf, amb = ck_route.classify(prompt, CFG)
    ok = tier == expected
    mark = "ok" if ok else "FAIL"
    print(f"[{mark}] {expected:>6} <- got {tier:<6} : {prompt!r}  ({reason})")
    if not ok:
        failures.append((prompt, expected, tier))

# Empty prompt -> default tier, never crashes.
tier, *_ = ck_route.classify("", CFG)
assert tier == CFG["default_tier"], "empty prompt should return default tier"
print(f"[ok] empty prompt -> {tier} (default)")

if failures:
    print(f"\n{len(failures)} FAILURES")
    sys.exit(1)
print(f"\nAll {len(CASES) + 1} route cases passed.")
