#!/usr/bin/env python3
"""Stop hook: when the turn ends, check usage and (if near the limit) drop a status
message into the chat so CLAUDE can decide whether to finish or schedule a resume.

Throttled to once per ~30 min per session so it doesn't nag every turn. Any error
degrades to a no-op — it must never block the session from stopping.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
BIN = os.path.join(ROOT, "bin")
CACHE = os.path.join(ROOT, ".ck-cache")
THROTTLE_SEC = 30 * 60

try:
    from ck_config import load_config
except Exception:
    def load_config():
        return {"autoswitch": False}


def _noop():
    print(json.dumps({}))
    sys.exit(0)


def _apply_pending_switch(session):
    """Apply a model switch queued by the prompt hook, now that the turn is done
    and the pane is idle (safe to send /model). Silent no-op if nothing queued."""
    if not load_config().get("autoswitch"):
        return
    safe = "".join(c for c in session if c.isalnum() or c in "._-") or "default"
    pf = os.path.join(CACHE, "pending-switch-" + safe)
    try:
        with open(pf) as f:
            tier = f.read().strip()
    except OSError:
        return
    if tier:
        try:
            subprocess.run(
                [os.path.join(BIN, "ck-switch"), tier, "--session", session],
                capture_output=True, text=True, timeout=8,
            )
        except Exception:
            pass
    try:
        os.remove(pf)
    except OSError:
        pass


def _throttled(session):
    os.makedirs(CACHE, exist_ok=True)
    marker = os.path.join(CACHE, "usage-notified-" + "".join(c for c in session if c.isalnum() or c in "._-"))
    now = time.time()
    try:
        if now - os.path.getmtime(marker) < THROTTLE_SEC:
            return True
    except OSError:
        pass
    try:
        with open(marker, "w") as f:
            f.write(str(now))
    except OSError:
        pass
    return False


def main():
    if os.environ.get("CK_INTERNAL"):  # inner classifier session — do nothing
        _noop()
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    session = str(data.get("session_id") or "default")

    # Apply any model switch queued on the first prompt (pane is idle now).
    _apply_pending_switch(session)

    try:
        out = subprocess.run(
            [os.path.join(BIN, "ck-usage")], capture_output=True, text=True, timeout=15
        ).stdout
        u = json.loads(out)
    except Exception:
        _noop()

    if not u.get("near_limit"):
        _noop()
    if _throttled(session):
        _noop()

    pct = u.get("five_hour_pct")
    resets = u.get("resets_at") or ""
    rin = u.get("resets_in_min")
    reset_h = (resets[11:16] + " UTC") if len(resets) >= 16 else "unknown"
    inm = ""
    if rin is not None:
        hh, mm = divmod(max(rin, 0), 60)
        inm = f" (in {hh}h{mm:02d}m)"
    qual = "" if u.get("source") == "api" else " (local estimate)"

    ctx = (
        f"[claude_knows usage] ⏳ You are at {pct}% of your 5-hour usage window{qual} "
        f"(resets {reset_h}{inm}). Decide for yourself: if substantial work is still "
        f"queued, invoke the `claude-knows` skill to schedule a resume at the reset time and then "
        f"pause; if you're nearly done, just finish and ignore this."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ctx}}))


if __name__ == "__main__":
    main()
