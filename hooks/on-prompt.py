#!/usr/bin/env python3
"""UserPromptSubmit hook: route the prompt to a model, surface it, optionally switch.

Reads the hook JSON on stdin (userPrompt, session_id), runs ck-route, and returns
`additionalContext` (for Claude) + `systemMessage` (for the user). If autoswitch is
enabled it also calls ck-switch (real live switch when in tmux). Never blocks the
prompt; any internal error degrades to an empty (no-op) hook result.
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


def _noop():
    print(json.dumps({}))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    prompt = data.get("userPrompt") or data.get("prompt") or ""
    session = str(data.get("session_id") or "default")
    if not prompt.strip():
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
                switched_note = f" (auto-switched via {swj.get('method')}; takes effect on your next prompt)"
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

    print(json.dumps({
        "systemMessage": sysmsg,
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx},
    }))


if __name__ == "__main__":
    main()
