#!/usr/bin/env python3
"""SessionStart hook: optionally switch the model BEFORE you type anything.

This answers "switch before I even say hi". With an empty conversation there is
nothing cached, so the switch happens cleanly with no "Switch model?" dialog. It
only does anything when a fixed start model is configured (config `start_model`
or env CK_START_MODEL) — there is no task yet to pick from, so it can only apply
a preference you set in advance. When set, it also marks the session as routed so
the per-prompt picker stays quiet (you chose a fixed model for this session).
"""
import json
import os
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
try:
    from ck_config import load_config, state_dir
except Exception:
    def load_config():
        return {}

    def state_dir():
        d = os.path.join(os.path.expanduser("~"), ".cache", "claude_knows")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d

BIN = os.path.join(ROOT, "bin")
CACHE = state_dir()


def _noop():
    print(json.dumps({}))
    sys.exit(0)


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def main():
    if os.environ.get("CK_INTERNAL"):
        _noop()
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    session = str(data.get("session_id") or "default")

    cfg = load_config()
    start_model = os.environ.get("CK_START_MODEL") or cfg.get("start_model")
    if not start_model or start_model not in ("haiku", "sonnet", "opus"):
        _noop()
    if not (cfg.get("autoswitch") and os.environ.get("TMUX")):
        _noop()

    # Switch now (empty conversation → no confirmation dialog), then mark the session
    # routed so the per-prompt picker won't switch again this session.
    try:
        subprocess.run(
            [os.path.join(BIN, "ck-switch"), start_model, "--session", session],
            capture_output=True, text=True, timeout=8,
        )
    except Exception:
        pass
    try:
        safe = "".join(c for c in session if c.isalnum() or c in "._-") or "default"
        os.makedirs(CACHE, exist_ok=True)
        open(os.path.join(CACHE, "routed-" + safe), "w").close()
    except OSError:
        pass

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"[claude_knows] Session started on your configured model: {start_model}.",
        }
    }))


if __name__ == "__main__":
    main()
