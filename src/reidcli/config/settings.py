"""Claude-Code-style settings file support.

Reads a settings.json shaped like Claude Code's (an `env` block of key/values)
and applies that block to the process environment. This is how ReidVerse-Cli
picks up the Reidchat proxy credentials — ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL
/ ANTHROPIC_MODEL — so the Anthropic provider routes through the Reidchat backend
instead of hitting api.anthropic.com directly.

Path resolution (first hit wins):
  1. $REIDCHAT_SETTINGS   (override)
  2. E:/leech/Reidchat.json   (default)

The settings file is authoritative: its `env` block overrides any ambient
environment for this process. This matters because an interactive shell profile
may pre-set ANTHROPIC_BASE_URL/ANTHROPIC_API_KEY to a different backend; without
overriding, ReidVerse-Cli would silently use that instead of Reidchat. Only this
process's os.environ is touched — the shell/profile is unaffected.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from reidcli.diagnostics.logger import get_logger

log = get_logger("reidcli.config.settings")

DEFAULT_SETTINGS_PATH = Path("E:/leech/Reidchat.json")


def settings_path() -> Path:
    """Resolve the settings file path ($REIDCHAT_SETTINGS or the default)."""
    override = os.environ.get("REIDCHAT_SETTINGS", "").strip()
    return Path(override) if override else DEFAULT_SETTINGS_PATH


def apply_settings_env(path: Path | None = None) -> dict[str, str]:
    """Apply a settings file's `env` block to os.environ.

    Returns the mapping of env vars that were actually applied (i.e. weren't
    already set in the environment). Missing/invalid files are a no-op.
    """
    path = path or settings_path()
    if not path.exists():
        log.debug("settings file not found: %s", path)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("failed to read settings %s: %s", path, exc)
        return {}

    env = data.get("env")
    if not isinstance(env, dict):
        return {}

    applied: dict[str, str] = {}
    for key, value in env.items():
        if value is None:
            continue
        new = str(value)
        if os.environ.get(key) not in (None, new):
            log.debug("settings override %s (ambient env replaced by %s)", key, path)
        os.environ[key] = new  # the settings file is authoritative
        applied[key] = new

    if applied:
        log.debug("applied %d env var(s) from %s: %s", len(applied), path, ", ".join(applied))
    return applied
