"""Centralized theme: colors, styles, and visual constants.

ReidVerse-Cli wears a Claude-Code-style skin in a red palette:
  - dark technical feel, high contrast
  - rounded borders, ⏺ bullets, ⎿ tree connectors
  - clean density over decorative excess

All UI modules should pull colors + glyphs from here so the look stays consistent.
"""
from __future__ import annotations

from rich import box
from rich.text import Text

# Brand.
APP_NAME = "ReidVerse-Cli"

# Core palette — red-forward, high-contrast.
PRIMARY = "#ff5f5f"       # brand, assistant, headers  (brand red)
SECONDARY = "#d75f5f"     # secondary accents
DIM = "dim"               # labels, metadata
SUCCESS = "green"         # ok, completed
WARN = "yellow"           # active, prompts, warnings
DANGER = "red"            # errors, failed, blocked
MUTED = "magenta"         # special states

# Claude-Code-style glyphs. Use text-presentation code points (not emoji) so the
# terminal renders them flat and honors the Rich style color. U+23FA (⏺) is an
# emoji and renders as a fixed-color double-width blob — avoid it.
SPARKLE = "✻"             # welcome banner + thinking mark
BULLET = "●"              # assistant / tool-call bullet  (U+25CF, text circle)
TREE = "⎿"                # tool-result connector
PROMPT = "›"              # input prompt caret

# Default border box for panels/tables.
BOX = box.ROUNDED

# Role icons for transcript display.
ROLE_ICON = {
    "system": "§",
    "user": "›",
    "assistant": BULLET,
    "tool": TREE,
}

ROLE_STYLE = {
    "system": DIM,
    "user": "bold",
    "assistant": PRIMARY,
    "tool": SUCCESS,
}

# Status badge styles.
STATUS_STYLE = {
    "completed": SUCCESS,
    "active": WARN,
    "failed": DANGER,
    "blocked": MUTED,
    "pending": DIM,
    "skipped": DIM,
    "archived": DIM,
}

# Risk colors.
RISK_STYLE = {
    "low": SUCCESS,
    "medium": WARN,
    "high": DANGER,
}

# Permission mode colors.
MODE_STYLE = {
    "strict": DANGER,
    "balanced": WARN,
    "autonomous": SUCCESS,
    "custom": MUTED,
}


# Visual constants.
MAX_WIDTH = 80  # constrain panels/tables so they don't span ultra-wide terminals


def badge(text: str, color: str) -> Text:
    """A compact colored badge like [ok] or [strict]."""
    return Text(f"[{text}]", style=color)


def label_value(label: str, value: str, label_color: str = DIM) -> Text:
    """A dim-label followed by a value:  session abc123."""
    return Text.assemble((f"{label} ", label_color), value)
