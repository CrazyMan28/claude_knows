#!/usr/bin/env bash
# claude_knows installer — Linux & macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/CrazyMan28/claude_knows/main/install.sh | bash
#
# Installs the plugin into Claude Code via the standard plugin CLI (no manual
# clone needed).
set -euo pipefail

REPO_URL="https://github.com/CrazyMan28/claude_knows"
MARKET="claude_knows"          # marketplace name (from .claude-plugin/marketplace.json)
PLUGIN="claude-knows@${MARKET}"

c_say(){ printf '\033[1;36m[claude_knows]\033[0m %s\n' "$1"; }
c_warn(){ printf '\033[1;33m[warn]\033[0m %s\n' "$1"; }
c_die(){ printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2; exit 1; }

case "$(uname -s)" in
  Linux)  OS=linux ;;
  Darwin) OS=mac ;;
  *) c_die "unsupported OS: $(uname -s) (Linux and macOS only)" ;;
esac
c_say "installing on ${OS} into Claude Code"

command -v claude  >/dev/null 2>&1 || c_die "the 'claude' CLI is required — https://code.claude.com"
command -v python3 >/dev/null 2>&1 || c_die "python3 is required (the plugin's engines are Python)"

# Add the marketplace (idempotent) then install the plugin.
c_say "adding marketplace…"
claude plugin marketplace add "$REPO_URL" >/dev/null 2>&1 \
  || claude plugin marketplace update "$MARKET" >/dev/null 2>&1 \
  || c_warn "marketplace already present or update skipped"

c_say "installing plugin…"
claude plugin install "$PLUGIN" --scope user

# Verify it actually landed and is enabled (don't just assume the install worked).
c_say "verifying…"
if claude plugin list 2>/dev/null | grep -A4 -F "$PLUGIN" | grep -qiE "enabled|✔"; then
  c_say "verified: $PLUGIN is enabled ✔"
else
  c_warn "installed, but couldn't confirm it's enabled — check with: claude plugin list"
fi

# Optional-capability advice.
if [ "$OS" = linux ]; then
  command -v at >/dev/null 2>&1 || c_warn "'at' not found — self-resume will use a detached-timer fallback (install 'at' for cleaner scheduling)."
fi

# Wire `claude` to auto-launch inside tmux with live model-switching ON.
# Skip with CK_NO_WRAPPER=1; skipped automatically if tmux isn't installed.
WRAP_ADDED=""
if [ -n "${CK_NO_WRAPPER:-}" ]; then
  c_say "CK_NO_WRAPPER set — skipping the tmux auto-launch wrapper."
elif ! command -v tmux >/dev/null 2>&1; then
  c_warn "tmux not installed — skipped the auto-tmux wrapper. Plugin still works (suggest-mode)."
else
  case "${SHELL:-sh}" in
    *zsh)  RC="$HOME/.zshrc" ;;
    # macOS Terminal runs login shells → ~/.bash_profile; Linux interactive → ~/.bashrc
    *bash) [ "$OS" = mac ] && RC="$HOME/.bash_profile" || RC="$HOME/.bashrc" ;;
    *)     RC="$HOME/.profile" ;;
  esac
  MARK="# >>> claude_knows wrapper >>>"
  if [ -f "$RC" ] && grep -qF "$MARK" "$RC" 2>/dev/null; then
    c_say "tmux auto-launch wrapper already present in $RC"
  else
    cat >> "$RC" <<'WRAP'

# >>> claude_knows wrapper >>>
# Auto-launch `claude` inside tmux with claude_knows live model-switching ON.
# One-off without tmux:  CK_NO_TMUX=1 claude    •    Remove: delete this block.
claude() {
  if [ -n "$TMUX" ] || [ -n "$CK_NO_TMUX" ] || ! command -v tmux >/dev/null 2>&1; then
    CK_AUTOSWITCH=1 command claude "$@"
  else
    tmux new-session -A -s claude "CK_AUTOSWITCH=1 command claude ${*}"
  fi
}
# <<< claude_knows wrapper <<<
WRAP
    WRAP_ADDED="$RC"
    c_say "added tmux auto-launch wrapper to $RC"
  fi
fi

cat <<EOF

$(c_say "installed ✔")

Next steps
  • Reload your shell:   exec \$SHELL      (or open a new terminal)
  • Just run:            claude           → opens in tmux with live model-switching ON
  • Your FIRST real prompt of a session → Haiku reads it and picks the model (~5s, once).
    Greetings ("hi") are ignored. A ⏳ warning appears near your REAL usage limit.
  • Real usage anytime:  claude plugin details ${PLUGIN}

One-offs / toggles:  CK_NO_TMUX=1 claude   CK_ROUTER_LLM=0 (heuristics-only)   CK_NEAR_LIMIT_PCT=80   CK_QUIET=1
Uninstall:  claude plugin uninstall ${PLUGIN}${WRAP_ADDED:+  (then delete the claude_knows block in $WRAP_ADDED)}
EOF
