# claude_knows — status

_Last updated: 2026-07-03_

**Project:** Claude Code plugin. Owner: CrazyMan28. Tracker id: `proj-6225f0ce`.
**Repo:** https://github.com/CrazyMan28/claude_knows (**public**).
**Installed:** enabled in the `claude2` instance (`~/.claude-secondary`) as `claude-knows@claude_knows`, user scope — active next session start.

## Summary

Two features, both built and locally verified:
1. **Auto model-picker** — prompt → Haiku/Sonnet/Opus, with real live switching in tmux.
2. **Usage self-awareness** — reads local transcripts, injects a near-limit status, Claude decides + self-schedules a resume.

## Component status

| Component | State | Verified by |
|---|---|---|
| `bin/ck-route` (router engine) | ✅ done | `tests/test_ck_route.py` (12/12) + CLI smoke |
| `bin/ck-switch` (live model switch) | ✅ done | real `tmux send-keys` injected `/opus` into a live pane |
| `bin/ck-usage` (usage engine) | ✅ done | **REAL** via `GET /api/oauth/usage` (verified: 69% / resets 12:29am, matches `/usage`); JSONL estimate fallback; tests 11/11 |
| `install.sh` (Linux/macOS one-liner) | ✅ done | `bash -n` clean; uses `claude plugin marketplace add` + `install` |
| `bin/ck-schedule-resume` (self-resume) | ✅ done | real `at` job scheduled, verified in `atq`, then removed |
| `hooks/on-prompt.py` (UserPromptSubmit) | ✅ done | **first-prompt-only** per session (marker file); verified: 1st→suggests, 2nd/3rd→silent, new session→suggests again |
| `hooks/on-stop.py` (Stop) | ✅ done | idle→no-op, forced near-limit→inject, throttle→no-op |
| `skills/claude-knows/SKILL.md` | ✅ done | decision guide for model + usage signals |
| `config/ck.config.json` + env overrides | ✅ done | loaded by `lib/ck_config.py` |
| README + diagrams, LICENSE | ✅ done | mermaid architecture + 2 sequence diagrams |

## Verified facts it relies on

- Live model switch: only `/model` (or its `/opus`-style shortcuts) switches mid-session; `settings.json` `model` is read once at startup (no hot-reload). ✅ handled via `tmux send-keys`.
- Hooks can inject `additionalContext`/`systemMessage` but **cannot** run `/model` themselves. ✅ design accounts for this.
- Local transcripts at `~/.claude/projects/**/*.jsonl` carry `usage` tokens + `model` + `timestamp`. ✅ confirmed on this machine.

## Known limitations (by design)

- No silent switching of the **main** session's model without tmux/xdotool/AppleScript.
- Usage % is now **real** (from `/api/oauth/usage`, same source as `/usage`). The local-JSONL path is only a fallback for when the OAuth token is missing/expired/offline, and that fallback is an estimate.
- Auto-switch applies to your **next** prompt (the current turn's model is already fixed) and is safest when the pane is idle.

## Next / optional (Phase D)

- [ ] Custom **Channel** MCP server for continuous mid-task usage injection (not just at turn end).
- [ ] `monitors/monitors.json` background poller for long-running tasks.
- [ ] Weekly-window ceiling learning + a weekly near-limit signal.
- [ ] Optional cost-weighting of cache tokens for a tighter limit estimate.
- [ ] Live-session end-to-end test inside a real `claude --plugin-dir` tmux run.
