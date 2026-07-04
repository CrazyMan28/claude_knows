#!/usr/bin/env python3
"""Tests for ck-usage. Run: python3 tests/test_ck_usage.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

_loader = SourceFileLoader("ck_usage", os.path.join(ROOT, "bin", "ck-usage"))
_spec = importlib.util.spec_from_loader("ck_usage", _loader)
ck_usage = importlib.util.module_from_spec(_spec)
_loader.exec_module(ck_usage)

failures = []


def check(name, cond):
    print(f"[{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        failures.append(name)


# --- unit: token summing across the 4 usage fields ---
toks = ck_usage._msg_tokens(
    {"input_tokens": 10, "output_tokens": 20, "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40}
)
check("_msg_tokens sums all four fields (=100)", toks == 100)

# --- unit: block grouping splits on a >window gap ---
win = timedelta(hours=5)
t0 = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)
events = [
    (t0, 100),
    (t0 + timedelta(minutes=30), 100),
    (t0 + timedelta(hours=8), 200),          # gap 7.5h -> new block
    (t0 + timedelta(hours=8, minutes=30), 50),
]
blocks = ck_usage.build_blocks(events, win)
check("gap splits into 2 blocks", len(blocks) == 2)
check("block1 tokens = 200", blocks[0]["tokens"] == 200)
check("block2 tokens = 250", blocks[1]["tokens"] == 250)

# --- end-to-end: fixture -> subprocess -> JSON assertions ---
NOW = "2026-07-03T22:00:00Z"


def line(ts, i, o, cc=0, cr=0):
    return json.dumps({
        "timestamp": ts,
        "message": {"model": "claude-opus-4-8",
                    "usage": {"input_tokens": i, "output_tokens": o,
                              "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr}},
    })


with tempfile.TemporaryDirectory() as d:
    proj = os.path.join(d, "-home-user-proj")
    os.makedirs(proj)
    with open(os.path.join(proj, "s.jsonl"), "w") as f:
        f.write(line("2026-07-03T12:00:00Z", 100000, 50000, 150000, 100000) + "\n")  # old block: 400k
        f.write(line("2026-07-03T20:00:00Z", 60000, 40000) + "\n")                    # active: 100k
        f.write(line("2026-07-03T21:00:00Z", 100000, 50000, 50000) + "\n")            # active: 200k
        f.write(line("2026-07-03T21:50:00Z", 30000, 20000) + "\n")                    # active: 50k

    out = subprocess.check_output(
        [sys.executable, os.path.join(ROOT, "bin", "ck-usage"), "--root", d, "--now", NOW],
        text=True,
    )
    r = json.loads(out)

check("active window tokens = 350000", r["window_tokens"] == 350000)
check("auto-learned ceiling = 400000 (historical max block)", r["ceiling_tokens"] == 400000)
check("used pct = 87.5", r["window_used_pct"] == 87.5)
check("near_limit true (>=80%)", r["near_limit"] is True)
check("resets in ~180 min", 178 <= r["resets_in_min"] <= 181)
check("resets_at is 2026-07-04T01:00", r["resets_at"].startswith("2026-07-04T01:00"))
check("weekly tokens = 750000 (all four msgs)", r["weekly_tokens"] == 750000)

if failures:
    print(f"\n{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("\nAll ck-usage tests passed.")
