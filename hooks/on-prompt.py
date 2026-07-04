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
import time

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
try:
    from ck_config import load_config, state_dir
except Exception:
    def load_config():
        return {"autoswitch": False, "quiet": False, "default_tier": "sonnet"}

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


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _preswitch(session, slash, prompt):
    """In tmux: type `/model X`+Enter, then re-type the user's prompt+Enter, so the
    prompt runs on the freshly-switched model. Returns True if the keystrokes were
    sent (caller then blocks the current turn). The re-typed prompt re-enters this
    hook, but the session marker is already set, so it no-ops (no loop, no re-pick)."""
    pane = os.environ.get("TMUX_PANE")
    base = ["tmux", "send-keys"] + (["-t", pane] if pane else [])
    try:
        subprocess.run(base + ["-l", slash], timeout=5)
        subprocess.run(base + ["Enter"], timeout=5)
        time.sleep(0.5)
        subprocess.run(base + ["-l", prompt], timeout=5)
        subprocess.run(base + ["Enter"], timeout=5)
        return True
    except Exception:
        return False


def typed_prompt_count(transcript_path):
    """Count real typed user prompts already in this session's transcript (Claude
    Code's own record). Tool-result messages have role 'user' too, so we skip those.
    Authoritative and reinstall-proof; returns -1 if the transcript can't be read."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return -1
    n = 0
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or '"user"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "user":
                    continue
                content = (d.get("message") or {}).get("content")
                if isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                ):
                    continue  # tool result, not a typed prompt
                n += 1
    except OSError:
        return -1
    return n


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
    # then stay silent for the rest of the session.
    #
    # Two independent guards so this can't misfire:
    #  1) a per-session marker in ~/.cache (survives plugin reinstalls), and
    #  2) the transcript itself — if Claude Code already recorded >=2 typed prompts
    #     this session, we're clearly mid-session even if the marker was wiped.
    marker = _marker(session)
    if os.path.exists(marker):
        _noop()
    if typed_prompt_count(data.get("transcript_path")) >= 2:
        # Backstop for a wiped marker: definitely not the first prompt. Record it
        # so the fast path handles the rest of the session, then stay silent.
        try:
            os.makedirs(CACHE, exist_ok=True)
            open(marker, "w").close()
        except OSError:
            pass
        _noop()

    # Greetings / acks ("hi", "thanks", "how are you") are not tasks. Don't pick a
    # model off them and don't spend the one-shot — wait for the first real prompt.
    if is_chitchat(prompt):
        _noop()

    # Mark this session as handled BEFORE the (slow) model call, so no later prompt
    # in this session can route even if the routing below takes a few seconds.
    try:
        os.makedirs(CACHE, exist_ok=True)
        open(marker, "w").close()
    except OSError:
        pass

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

    # PRE-SWITCH (opt-in, CK_PRESWITCH=1): so your FIRST task runs on the right model,
    # switch NOW and re-run this exact prompt on the new model — blocking the current
    # turn so nothing runs on the wrong one. Only in tmux, only when the pick differs
    # from where the session starts, and only for a single-line prompt (multi-line is
    # unsafe to re-type via send-keys). Falls through to the safe queued path otherwise.
    default_tier = cfg.get("default_tier", "sonnet")
    if (
        cfg.get("autoswitch")
        and _truthy(os.environ.get("CK_PRESWITCH"))
        and os.environ.get("TMUX")
        and tier != default_tier
        and "\n" not in prompt
        and len(prompt) <= 400
    ):
        if _preswitch(session, slash, prompt):
            print(json.dumps({
                "systemMessage": f"🧭 claude_knows: switching to {slash} and re-running your prompt on it…",
                "continue": False,
                "stopReason": f"claude_knows: switched to {tier} — re-running your prompt on the right model.",
            }))
            return

    # Otherwise: queue the switch for when THIS turn finishes (Stop hook applies it
    # while the pane is idle — sending /model mid-prompt would collide with the submit).
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

    print(json.dumps({
        "systemMessage": sysmsg,
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx},
    }))


if __name__ == "__main__":
    main()
