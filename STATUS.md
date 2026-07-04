# claude_knows — status

_Last updated: 2026-07-03_

**Project:** private plugin for Claude Code. Owner: CrazyMan28. Tracker id: `proj-6225f0ce`.

## Summary

Two features, both built and locally verified:
1. **Auto model-picker** — prompt → Haiku/Sonnet/Opus, with real live switching in tmux.
2. **Usage self-awareness** — reads local transcripts, injects a near-limit status, Claude decides + self-schedules a resume.

## Component status

| Component | State | Verified by |
|---|---|---|
| `bin/ck-route` (router engine) | ✅ done | `tests/test_ck_route.py` (12/12) + CLI smoke |
| `bin/ck-switch` (live model switch) | ✅ done | real `tmux send-keys` injected `/opus` into a live pane |
| `bin/ck-usage` (usage engine) | ✅ done | `tests/test_ck_usage.py` (11/11) + run on real 2,675-msg history |
| `bin/ck-schedule-resume` (self-resume) | ✅ done | real `at` job scheduled, verified in `atq`, then removed |
| `hooks/on-prompt.py` (UserPromptSubmit) | ✅ done | simulated hook stdin → correct suggestion JSON |
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
- Usage % is an **estimate** (Anthropic doesn't publish exact plan ceilings); auto-learned from your own history.
- Auto-switch applies to your **next** prompt (the current turn's model is already fixed) and is safest when the pane is idle.

## Next / optional (Phase D)

- [ ] Custom **Channel** MCP server for continuous mid-task usage injection (not just at turn end).
- [ ] `monitors/monitors.json` background poller for long-running tasks.
- [ ] Weekly-window ceiling learning + a weekly near-limit signal.
- [ ] Optional cost-weighting of cache tokens for a tighter limit estimate.
- [ ] Live-session end-to-end test inside a real `claude --plugin-dir` tmux run.
