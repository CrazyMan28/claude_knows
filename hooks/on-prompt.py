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
import re
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


def _safe(session):
    return "".join(c for c in session if c.isalnum() or c in "._-") or "default"


def _marker(session):
    return os.path.join(CACHE, "routed-" + _safe(session))


def _pending(session):
    return os.path.join(CACHE, "pending-switch-" + _safe(session))


# Greetings / acknowledgements — not tasks, so they must NOT pick a model.
_GREET = {
    "hi", "hii", "hiya", "hello", "helo", "hey", "heya", "yo", "sup", "howdy",
    "hullo", "greetings", "morning", "afternoon", "evening", "gm", "ge", "wave",
    "thanks", "thank", "thankyou", "thx", "ty", "cheers",
    "ok", "okay", "k", "kk", "cool", "nice", "great", "awesome", "sweet", "word",
    "lol", "lmao", "haha", "hehe", "yes", "yep", "yeah", "ya", "no", "nope",
    "sure", "hmm", "hm", "test", "testing", "ping", "wassup", "wsp", "howdy",
}
_FILLER = {
    "there", "claude", "please", "pls", "man", "bro", "dude", "mate", "buddy",
    "again", "u", "you", "a", "an", "the", "good", "is", "it", "im", "i'm",
    "up", "whats", "what's", "what", "how", "are", "doing", "everything",
    "today", "just", "saying", "and", "so", "well", "hows", "how's", "to", "me",
}


def is_chitchat(prompt):
    """True if the prompt is only a greeting / acknowledgement (contains no task)."""
    words = re.findall(r"[a-z']+", prompt.lower())
    if not words:
        return True
    return all(w in _GREET or w in _FILLER for w in words)


def main():
    # Guard: the model-picker spawns `claude -p` internally; don't let that inner
    # session re-trigger this hook (infinite loop).
    if os.environ.get("CK_INTERNAL"):
        _noop()
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    prompt = data.get("userPrompt") or data.get("prompt") or ""
    session = str(data.get("session_id") or "default")
    if not prompt.strip():
        _noop()

    # Only act on the FIRST real prompt of a session — pick/switch the model once,
    # then stay silent for the rest of the session. The marker records that we fired.
    marker = _marker(session)
    if os.path.exists(marker):
        _noop()

    # Greetings / acks ("hi", "thanks", "how are you") are not tasks. Don't pick a
    # model off them and don't spend the one-shot — wait for the first real prompt.
    if is_chitchat(prompt):
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

    # Queue the switch to be applied when THIS turn finishes. Sending /model into
    # the pane mid-prompt is racy (it collides with the prompt being submitted), so
    # the Stop hook applies it while the pane is idle.
    switched_note = ""
    if cfg.get("autoswitch"):
        try:
            os.makedirs(CACHE, exist_ok=True)
            with open(_pending(session), "w") as f:
                f.write(tier)
            switched_note = f" (switching to {tier} after this reply)"
        except OSError:
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
