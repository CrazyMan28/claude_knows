"""Shared config + path helpers for claude_knows.

Every bin/ script imports this. It resolves the plugin root from its own
location so it works whether launched by a hook (absolute path) or by hand.
Config = defaults <- config/ck.config.json <- environment overrides.
"""
import json
import os

# Plugin root = parent of the dir holding this file (lib/ -> root).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "ck.config.json")

DEFAULTS = {
    "default_tier": "sonnet",
    "autoswitch": False,
    "router_llm_fallback": True,
    "quiet": False,
    "usage": {
        "window_hours": 5,
        "near_limit_pct": 80,
        "ceiling_mode": "auto-learn",
        "ceiling_tokens": None,
        "weekly_near_limit_pct": 85,
    },
    "tiers": {
        "haiku": {"model_id": "claude-haiku-4-5", "slash": "/haiku"},
        "sonnet": {"model_id": "claude-sonnet-5", "slash": "/sonnet"},
        "opus": {"model_id": "claude-opus-4-8", "slash": "/opus"},
    },
    "rules": {
        "haiku_max_len": 60,
        "opus_min_len_with_code": 600,
        "opus_keywords": [],
        "haiku_keywords": [],
    },
}

TIER_ORDER = ["haiku", "sonnet", "opus"]


def _deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _truthy(val):
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = _deep_merge(cfg, json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # defaults are a valid config on their own

    # Environment overrides win over the file.
    if "CK_AUTOSWITCH" in os.environ:
        cfg["autoswitch"] = _truthy(os.environ["CK_AUTOSWITCH"])
    if "CK_ROUTER_LLM" in os.environ:
        cfg["router_llm_fallback"] = _truthy(os.environ["CK_ROUTER_LLM"])
    if "CK_QUIET" in os.environ:
        cfg["quiet"] = _truthy(os.environ["CK_QUIET"])
    if os.environ.get("CK_NEAR_LIMIT_PCT"):
        try:
            cfg["usage"]["near_limit_pct"] = float(os.environ["CK_NEAR_LIMIT_PCT"])
        except ValueError:
            pass
    if os.environ.get("CK_CEILING_TOKENS"):
        try:
            cfg["usage"]["ceiling_tokens"] = int(os.environ["CK_CEILING_TOKENS"])
            cfg["usage"]["ceiling_mode"] = "fixed"
        except ValueError:
            pass
    return cfg


def tier_info(cfg, tier):
    """Return {'tier','model_id','slash'} for a tier name, falling back safely."""
    tiers = cfg.get("tiers", DEFAULTS["tiers"])
    info = tiers.get(tier) or tiers.get(cfg.get("default_tier", "sonnet")) or {}
    return {
        "tier": tier,
        "model_id": info.get("model_id", ""),
        "slash": info.get("slash", "/" + tier),
    }


def transcript_root():
    """Where Claude Code stores per-project session JSONL transcripts."""
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


def config_dir():
    """The active Claude Code config dir. Claude Code does not always pass
    CLAUDE_CONFIG_DIR through to hooks, so fall back to deriving it from
    CLAUDE_PLUGIN_ROOT (…/<config-dir>/plugins/cache/…), then ~/.claude."""
    d = os.environ.get("CLAUDE_CONFIG_DIR")
    if d:
        return d
    root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    i = root.find(os.sep + "plugins" + os.sep)
    if i > 0:
        return root[:i]
    return os.path.join(os.path.expanduser("~"), ".claude")


def settings_path():
    """This session's settings.json."""
    return os.path.join(config_dir(), "settings.json")


def read_default_model():
    """The persisted default model in settings.json, or None."""
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            return (json.load(f) or {}).get("model")
    except (OSError, json.JSONDecodeError):
        return None


def write_default_model(model):
    """Set the persisted default model in settings.json (best-effort)."""
    p = settings_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        d["model"] = model
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        return True
    except (OSError, json.JSONDecodeError):
        return False


def state_dir():
    """Stable, writable dir for per-session state (markers, pending switches).

    Deliberately OUTSIDE the plugin install dir, which gets wiped on plugin
    update/re-sync — that would reset the 'first message' marker mid-session.
    """
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    d = os.path.join(base, "claude_knows")
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except OSError:
        d = "/tmp/claude_knows"
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d
