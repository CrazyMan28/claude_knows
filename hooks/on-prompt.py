#!/usr/bin/env python3
"""UserPromptSubmit hook: on the FIRST prompt of a session, route it to a model.

Reads the hook JSON on stdin (userPrompt, session_id), runs ck-route on your first
prompt, returns `additionalContext` (for Claude) + `systemMessage` (for the user),
and — if autoswitch is on — calls ck-switch (real live switch when in tmux). It only
fires once per session (a per-session marker records it); every prompt after the
first is a silent no-op. Any internal error degrades to an empty (no-op) result.
"""
import json
import os
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
try:
    from ck_config import load_config
except Exception:
    def load_config():
        return {"autoswitch": False, "quiet": False, "default_tier": "sonnet"}

BIN = os.path.join(ROOT, "bin")
CACHE = os.path.join(ROOT, ".ck-cache")


def _noop():
    print(json.dumps({}))
    sys.exit(0)


def _marker(session):
    safe = "".join(c for c in session if c.isalnum() or c in "._-") or "default"
    return os.path.join(CACHE, "routed-" + safe)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    prompt = data.get("userPrompt") or data.get("prompt") or ""
    session = str(data.get("session_id") or "default")
    if not prompt.strip():
        _noop()

    # Only act on the FIRST prompt of a session — pick/switch the model once, then
    # stay silent for the rest of the session. The marker file records that we fired.
    marker = _marker(session)
    if os.path.exists(marker):
        _noop()

    cfg = load_config()
    try:
        out = subprocess.run(
            [os.path.join(BIN, "ck-route")], input=prompt,
            capture_output=True, text=True, timeout=15,
        ).stdout
        route = json.loads(out)
    except Exception:
        _noop()

    tier = route.get("tier", "sonnet")
    slash = route.get("slash", "/" + tier)
    reason = route.get("reason", "")
    model_id = route.get("model_id", "")

    switched_note = ""
    if cfg.get("autoswitch"):
        try:
            sw = subprocess.run(
                [os.path.join(BIN, "ck-switch"), tier, "--session", session],
                capture_output=True, text=True, timeout=8,
            ).stdout
            swj = json.loads(sw)
            if swj.get("switched"):
                switched_note = f" (auto-switched via {swj.get('method')}; applies from your next prompt for the rest of the session)"
            elif swj.get("method") == "noop":
                switched_note = " (already on this model)"
        except Exception:
            pass

    # Quiet mode: stay silent when the pick is just the default and nothing was switched.
    if cfg.get("quiet") and tier == cfg.get("default_tier", "sonnet") and not switched_note:
        _noop()

    ctx = (
        f"[claude_knows] Best model for this task: {tier} ({model_id}) — {reason}.{switched_note} "
        f"If auto-switch is off, the user can press {slash} to switch this session. "
        f"When you dispatch subagents for this task, prefer model '{tier}'."
    )
    sysmsg = f"🧭 claude_knows: {slash} — {reason}{switched_note}"

    try:
        os.makedirs(CACHE, exist_ok=True)
        open(marker, "w").close()
    except OSError:
        pass

    print(json.dumps({
        "systemMessage": sysmsg,
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx},
    }))


if __name__ == "__main__":
    main()
