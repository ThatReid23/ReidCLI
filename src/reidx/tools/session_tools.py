"""Session-scoped tools the agent can use to fix harness metadata.

`set_context_window` lets the model correct the footer max-context meter when
the known table / provider /models metadata is wrong for the active model.
"""
from __future__ import annotations

from typing import Any

from reidx.policy.models import RiskLevel
from reidx.tools.base import BaseTool, ToolContext, ToolDefinition, ToolResult

_SET_CTX_PARAMS = {
    "type": "object",
    "properties": {
        "tokens": {
            "type": "integer",
            "description": (
                "Max context window size in tokens for the active model "
                "(e.g. 1000000 for 1M, 200000 for 200k, 128000 for 128k)."
            ),
        },
        "model": {
            "type": "string",
            "description": (
                "Optional model id to bind this window to. Defaults to the "
                "session's current model."
            ),
        },
    },
    "required": ["tokens"],
}


def _parse_tokens(raw: Any) -> int | None:
    """Accept int, or strings like '1M', '200k', '128000'."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        n = int(raw)
        return n if n >= 1024 else None
    s = str(raw).strip().lower().replace(",", "").replace("_", "")
    if not s:
        return None
    mult = 1
    if s.endswith("m"):
        mult = 1_000_000
        s = s[:-1]
    elif s.endswith("k"):
        mult = 1_000
        s = s[:-1]
    try:
        n = int(float(s) * mult)
    except ValueError:
        return None
    return n if n >= 1024 else None


class SetContextWindowTool(BaseTool):
    """Update the session footer max-context (used/max meter)."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="set_context_window",
            description=(
                "Set the max context window size shown in the status bar and used "
                "for auto-compact thresholds. Call this when the footer max is wrong "
                "for the active model (e.g. GLM-5.2 should be 1000000 / 1M, not 128000). "
                "Does not change the provider or model id — only the harness meter."
            ),
            parameters=_SET_CTX_PARAMS,
            risk=RiskLevel.LOW,
        )

    def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        tokens = _parse_tokens(args.get("tokens"))
        if tokens is None:
            return ToolResult.fail(
                "invalid tokens — pass an integer >= 1024, or a string like '1M' / '200k'"
            )
        # Hard ceiling so a typo can't set insane values that break compact math.
        if tokens > 16_000_000:
            return ToolResult.fail("tokens too large (max 16M)")

        orch = ctx.extra.get("orchestrator")
        if orch is None or getattr(orch, "state", None) is None:
            return ToolResult.fail("no active session")

        session = orch.state.session
        model = str(args.get("model") or "").strip() or (session.model or "")
        if not model:
            model = "unknown"

        from reidx.provider.context_windows import (
            fmt_context_window,
            remember_context,
        )

        # API-level stickiness so known-table seeds don't immediately overwrite.
        remember_context(model, tokens, from_api=True)
        session.context_window = tokens
        try:
            orch.session_store.update(session)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(f"updated live meter but failed to persist: {exc}")

        label = fmt_context_window(tokens)
        return ToolResult.ok_(
            f"context window set to {tokens} tokens ({label}) for model {model}",
            tokens=tokens,
            model=model,
            label=label,
        )


def register_session_tools(registry) -> None:  # type: ignore[no-untyped-def]
    registry.register(SetContextWindowTool())


__all__ = ["SetContextWindowTool", "register_session_tools"]
