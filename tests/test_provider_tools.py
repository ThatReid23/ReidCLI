"""Agent provider connect / use tools."""
from __future__ import annotations

from pathlib import Path

from reidx.config.models import default_config
from reidx.policy.engine import PolicyEngine
from reidx.provider.stub import StubProvider
from reidx.runtime.orchestrator import Orchestrator
from reidx.tools import default_registry
from reidx.tools.base import ToolContext
from reidx.tools.provider_tools import (
    ConnectProviderTool,
    ListConnectedProvidersTool,
    ListProviderCatalogTool,
    SetSessionModelTool,
    UseProviderTool,
)


def _ctx(orch, approve: bool = True) -> ToolContext:
    cfg = orch.config
    return ToolContext(
        workspace_root=cfg.workspace_root or Path("."),
        policy=PolicyEngine(cfg),
        approver=lambda _p: approve,
        extra={"orchestrator": orch},
    )


def test_provider_tools_registered() -> None:
    names = {d.name for d in default_registry().definitions()}
    for n in (
        "list_provider_catalog",
        "list_connected_providers",
        "connect_provider",
        "use_provider",
        "disconnect_provider",
        "set_model",
    ):
        assert n in names


def test_list_catalog_finds_opencode() -> None:
    r = ListProviderCatalogTool().execute({"query": "opencode"}, _ctx(
        Orchestrator(default_config(), StubProvider(), default_registry())
    ))
    assert r.ok
    assert "opencode-go" in r.output


def test_connect_and_use(tmp_path: Path) -> None:
    cfg = default_config()
    cfg.workspace_root = tmp_path
    cfg.storage_root = tmp_path / "store"
    orch = Orchestrator(cfg, StubProvider(), default_registry())
    orch.start_session(title="p")
    ctx = _ctx(orch, approve=True)

    r = ConnectProviderTool().execute(
        {
            "catalog_id": "opencode-go",
            "api_key": "sk-test-key-for-unit",
            "default_model": "glm-5.2",
            "activate": True,
        },
        ctx,
    )
    assert r.ok, r.error
    assert orch.providers is not None
    assert orch.providers.has("OpenCode Go")
    assert orch.state is not None
    assert orch.state.session.provider == "OpenCode Go"
    assert orch.state.session.model == "glm-5.2"

    listed = ListConnectedProvidersTool().execute({}, ctx)
    assert listed.ok
    assert "OpenCode Go" in listed.output

    r2 = UseProviderTool().execute({"provider": "stub"}, ctx)
    assert r2.ok
    assert orch.state.session.provider == "stub"

    r3 = SetSessionModelTool().execute({"model": "stub-v0"}, ctx)
    assert r3.ok
    assert orch.state.session.model == "stub-v0"


def test_connect_denied_without_approval(tmp_path: Path) -> None:
    cfg = default_config()
    cfg.workspace_root = tmp_path
    cfg.storage_root = tmp_path / "store"
    orch = Orchestrator(cfg, StubProvider(), default_registry())
    orch.start_session(title="p")
    ctx = _ctx(orch, approve=False)
    r = ConnectProviderTool().execute(
        {"catalog_id": "opencode-go", "api_key": "sk-x", "activate": False},
        ctx,
    )
    assert not r.ok
    assert "denied" in r.error.lower()
