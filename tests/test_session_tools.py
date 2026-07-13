"""Tests for set_context_window session tool."""
from __future__ import annotations

from pathlib import Path

from reidx.config.models import default_config
from reidx.policy.engine import PolicyEngine
from reidx.provider.context_windows import clear_live_cache, context_window_for
from reidx.provider.stub import StubProvider
from reidx.runtime.orchestrator import Orchestrator
from reidx.tools import default_registry
from reidx.tools.base import ToolContext
from reidx.tools.session_tools import SetContextWindowTool, _parse_tokens


def test_parse_tokens() -> None:
    assert _parse_tokens(128_000) == 128_000
    assert _parse_tokens("1M") == 1_000_000
    assert _parse_tokens("200k") == 200_000
    assert _parse_tokens("1.0m") == 1_000_000
    assert _parse_tokens(100) is None
    assert _parse_tokens("nope") is None


def test_set_context_window_updates_session(tmp_path: Path) -> None:
    clear_live_cache()
    cfg = default_config()
    cfg.workspace_root = tmp_path
    cfg.storage_root = tmp_path / "store"
    orch = Orchestrator(cfg, StubProvider(), default_registry())
    orch.start_session(title="ctx")
    orch.state.session.model = "deepseek-v4-pro"
    # Default table seed is 128k
    assert context_window_for("deepseek-v4-pro") == 128_000

    ctx = ToolContext(
        workspace_root=tmp_path,
        policy=PolicyEngine(cfg),
        extra={"orchestrator": orch},
    )
    result = SetContextWindowTool().execute({"tokens": "1M"}, ctx)
    assert result.ok, result.error
    assert orch.state.session.context_window == 1_000_000
    assert context_window_for("deepseek-v4-pro") == 1_000_000
    assert "1M" in result.output or "1000000" in result.output


def test_set_context_window_in_default_registry() -> None:
    names = {t.name for t in default_registry().definitions()}
    assert "set_context_window" in names
