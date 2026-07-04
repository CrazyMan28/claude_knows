#!/usr/bin/env python3
"""SessionEnd hook: restore the default model captured at SessionStart.

`/model X` persists X as your default for new sessions, so per-session auto-switching
would leave your default drifted (e.g. stuck on Opus). This puts it back to whatever
it was when the session started, so every new session starts on your real default.
Only active when autoswitch is on (the plugin is managing the model).
"""
import json
import os
import sys

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
try:
    from ck_config import load_config, state_dir, write_default_model
except Exception:
    def load_config():
        return {}

    def write_default_model(_m):
        return False

    def state_dir():
        d = os.path.join(os.path.expanduser("~"), ".cache", "claude_knows")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d

CACHE = state_dir()


def _done():
    print(json.dumps({}))
    sys.exit(0)


def main():
    if os.environ.get("CK_INTERNAL"):
        _done()
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    session = str(data.get("session_id") or "default")

    if not load_config().get("autoswitch"):
        _done()

    safe = "".join(c for c in session if c.isalnum() or c in "._-") or "default"
    marker = os.path.join(CACHE, "origmodel-" + safe)
    try:
        with open(marker, "r", encoding="utf-8") as f:
            orig = f.read().strip()
    except OSError:
        _done()

    if orig:
        write_default_model(orig)
    try:
        os.remove(marker)
    except OSError:
        pass
    _done()


if __name__ == "__main__":
    main()
