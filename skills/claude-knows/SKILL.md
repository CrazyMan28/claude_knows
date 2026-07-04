---
name: claude-knows
description: How to act on claude_knows signals — the model-routing suggestion injected on your first prompt of a session, and the usage-limit status injected when you're near your 5-hour window. Use when you see a "[claude_knows]" or "[claude_knows usage]" message, or when deciding which model to use or whether to pause and schedule a resume near the usage limit.
---

# claude_knows — acting on the signals

This plugin injects two kinds of messages into the conversation. Here's what to do with each.

## 1. Model routing signal

On the **first prompt of a session** (only) you may see:

> `[claude_knows] Best model for this task: opus (claude-opus-4-8) — hard-task keyword detected. ...`

What to do:
- **The plugin already surfaced the recommendation to the user** (a `🧭` line), once, at the start of the session. You do **not** need to repeat it.
- **If auto-switch is off** and the recommended tier clearly differs from the current model, you may briefly note that the user can press the slash command (e.g. `/opus`) to switch — but only once, don't nag.
- **When you dispatch subagents** (the Task/Agent tool) for this task, pass the suggested tier as the subagent's `model` (e.g. `model: "opus"`). This is the one place model selection is fully under your control, so honor the routing there.
- The pick came from **Haiku reading the prompt** (keyword heuristics are the offline fallback). If you can tell the task is harder/easier than the suggestion, trust your own judgement.

Tiers: `haiku` = trivial/lookup, `sonnet` = normal coding (default), `opus` = hard/architectural.

## 2. Usage-limit signal — YOU decide

When a turn ends near your limit you may see:

> `[claude_knows usage] ⏳ You are at 85% of your 5-hour usage window (resets 01:00 UTC, in 2h10m). Decide for yourself: ...`

**This is a judgement call, and it's yours.** Weigh how much work is left:

- **Nearly done** (a few small steps): just finish. Ignore the warning. Do NOT schedule anything.
- **Substantial work remains** (many steps, long build/migration): tell the user you're near the limit, then **schedule a resume at the reset time and pause**, so the work continues automatically when the window resets.

The percentage is the **real** number from the server (`/api/oauth/usage`, same as `/usage`) when your token is available; if it says "(local estimate)" it fell back to transcript math. Either way, treat it as "getting close, plan ahead," not a hard stop.

## Scheduling a resume

Two ways, pick one:

**A) Native scheduling (preferred for cloud/headless).** Use Claude Code's built-in one-off scheduling to create a routine at the reset time that continues the work. Give it a clear continue-prompt describing exactly what's left.

**B) Local scheduler (this plugin).** Run:

```
${CLAUDE_PLUGIN_ROOT}/bin/ck-schedule-resume \
  --at <reset time, e.g. 2026-07-04T01:00:00Z or +130m> \
  --prompt "<exactly what to continue: the remaining steps>" \
  --session <this session id> \
  --run
```

Add `--headless` to resume with `claude -p` (non-interactive). Without `--run` it prints a dry-run preview. It uses `at` if available, else a detached timer, and reads the prompt from a file so quotes/newlines are safe.

After scheduling, tell the user: what you scheduled, for when, and that the session will pick the work back up then. Then stop.

## Checking usage on demand

Run `${CLAUDE_PLUGIN_ROOT}/bin/ck-usage --pretty` any time to see current window %, reset time, burn rate, and weekly total.
