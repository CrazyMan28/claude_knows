#!/usr/bin/env bash
# claude_knows installer — Linux & macOS.
#
#   curl -fsSL https://raw.githubusercontent.com/CrazyMan28/claude_knows/main/install.sh | bash
#
# Installs the plugin into Claude Code via the standard plugin CLI (no manual
# clone needed). To install into a non-default config (e.g. a second Claude),
# prefix with CLAUDE_CONFIG_DIR, e.g.:
#   CLAUDE_CONFIG_DIR="$HOME/.claude-secondary" bash install.sh
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
c_say "installing on ${OS} (config: ${CLAUDE_CONFIG_DIR:-$HOME/.claude})"

command -v claude  >/dev/null 2>&1 || c_die "the 'claude' CLI is required — https://code.claude.com"
command -v python3 >/dev/null 2>&1 || c_die "python3 is required (the plugin's engines are Python)"

# Add the marketplace (idempotent) then install the plugin.
c_say "adding marketplace…"
claude plugin marketplace add "$REPO_URL" >/dev/null 2>&1 \
  || claude plugin marketplace update "$MARKET" >/dev/null 2>&1 \
  || c_warn "marketplace already present or update skipped"

c_say "installing plugin…"
claude plugin install "$PLUGIN" --scope user

# Optional-capability advice.
command -v tmux >/dev/null 2>&1 || c_warn "tmux not found — real live model auto-switch needs tmux (or xdotool on Linux / macOS Accessibility). Suggest-mode works without it."
if [ "$OS" = linux ]; then
  command -v at >/dev/null 2>&1 || c_warn "'at' not found — self-resume will use a detached-timer fallback (install 'at' for cleaner scheduling)."
fi

cat <<EOF

$(c_say "installed ✔")

Next steps
  • Restart Claude Code — plugins load at session start.
  • Each prompt shows a 🧭 model suggestion; a ⏳ warning appears near your usage limit.
  • For REAL live model switching, run inside tmux with autoswitch enabled:
        tmux
        CK_AUTOSWITCH=1 claude
  • Real usage anytime:   claude plugin details ${PLUGIN}   (or run bin/ck-usage --pretty from the install)

Toggles (env):  CK_AUTOSWITCH=1  CK_ROUTER_LLM=1  CK_NEAR_LIMIT_PCT=80  CK_QUIET=1
Uninstall:      claude plugin uninstall ${PLUGIN}
EOF
