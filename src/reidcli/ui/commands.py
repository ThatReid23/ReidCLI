"""Slash command routing for the REPL.

Each command returns a string hint for the REPL loop:
  "continue"  -> keep the loop running
  "exit"      -> stop the loop
Commands mutate orchestrator/state in place. Add new commands here — and add
a matching entry to SLASH_COMMANDS (or WORKFLOW_SUBCOMMANDS) below, which is
the single source both /help and the "/" completion menu (ui/app.py) render
from, so they can't drift out of sync.
"""
from __future__ import annotations

from pathlib import Path

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from reidcli.policy.models import PermissionMode
from reidcli.provider.store import SUPPORTED_KINDS, ProviderRecord, ProviderStore, build_provider
from reidcli.runtime.orchestrator import Orchestrator
from reidcli.ui import render
from reidcli.ui.theme import APP_NAME, BOX, PRIMARY
from reidcli.workflows.models import Workflow

_EFFORT_LEVELS = ("low", "medium", "high", "xhigh")

# (command, args-hint, description, help-group). Order here is display order.
SLASH_COMMANDS: list[tuple[str, str, str, str]] = [
    ("/status", "", "show current session + mode + tasks", "Session"),
    ("/sessions", "", "list all sessions", "Session"),
    ("/resume", "<id>", "resume a prior session", "Session"),
    ("/transcript", "[n]", "show last n messages (default 20)", "Session"),
    ("/rewind", "", "drop the last turn from state", "Session"),
    ("/tasks", "[status]", "list tasks (filter: pending|active|completed|failed|blocked)", "Tasks"),
    ("/model", "<name>", "set model for the session", "Config & Policy"),
    ("/effort", "<level>", "set reasoning effort (low|medium|high|xhigh)", "Config & Policy"),
    ("/mode", "<mode>", "set permission mode (strict|balanced|autonomous|custom)", "Config & Policy"),
    ("/nyx", "[on|off]", "toggle Nyx redteam/offensive-security persona", "Config & Policy"),
    ("/permissions", "", "show current policy + gates", "Config & Policy"),
    ("/tools", "", "list registered tools with risk levels", "Config & Policy"),
    ("/workflows", "", "list saved workflows", "Workflows"),
    ("/workflow", "<run|save|show|delete> ...", "manage saved workflows", "Workflows"),
    ("/providers", "", "list registered providers (stub is always default)", "Providers"),
    ("/connect", "<name> <kind> <base_url> [api_key] [model]", "add a provider (kind: anthropic|openai|openai-compatible|ollama)", "Providers"),
    ("/disconnect", "<name>", "remove a saved provider", "Providers"),
    ("/use", "<name>", "switch this session to a registered provider", "Providers"),
    ("/help", "", "show this help", "Meta"),
    ("/clear", "", "clear the screen", "Meta"),
    ("/exit", "", f"quit {APP_NAME}", "Meta"),
]

# (subcommand, args-hint, description) for "/workflow <subcommand>".
WORKFLOW_SUBCOMMANDS: list[tuple[str, str, str]] = [
    ("run", "<name>", "run a workflow's steps in sequence"),
    ("save", "<name> [n]", "save the last n user turns as a workflow (default 5)"),
    ("show", "<name>", "show a workflow's steps"),
    ("delete", "<name>", "delete a workflow"),
]


def _build_help() -> Group:
    def section(header: str, body: str) -> Text:
        # Text(..., style=...) applies to just the constructor's own content
        # (the header); .append() with no style keeps the body literal — this
        # avoids Text.from_markup(), which would otherwise parse literal "["
        # in args hints like "[n]"/"[status]" as (invalid) markup tags and
        # silently swallow them.
        text = Text(f"{header}\n", style="bold")
        text.append(f"{body}\n")
        return text

    groups: dict[str, list[str]] = {}
    for cmd, args, desc, group in SLASH_COMMANDS:
        left = f"{cmd} {args}".rstrip()
        groups.setdefault(group, []).append(f"  {left:<28} {desc}")

    parts = [Panel(Text(f"{APP_NAME} commands", style=f"bold {PRIMARY}"), box=BOX, border_style=PRIMARY, padding=(0, 2))]
    for group, lines in groups.items():
        parts.append(section(group, "\n".join(lines)))

    sub_lines = "\n".join(f"    /workflow {name:<8} {args:<14} {desc}" for name, args, desc in WORKFLOW_SUBCOMMANDS)
    parts.append(section("Workflow subcommands", sub_lines))

    parts.append(
        section(
            "Tip",
            "  Type / to see a completion menu for every command above — Tab/↓ to select, Enter to accept.",
        )
    )
    return Group(*parts)


HELP = _build_help()


def _set_mode(orchestrator: Orchestrator, value: str) -> bool:
    try:
        mode = PermissionMode(value)
    except ValueError:
        render.print_error(f"unknown mode: {value}")
        return False
    orchestrator.set_permission_mode(mode)
    render.print_info(f"mode → {mode.value}")
    return True


def _handle_nyx(orchestrator: Orchestrator, arg: str) -> None:
    value = arg.strip().lower()
    if not value:
        render.print_info(f"nyx: {'on' if orchestrator.nyx_enabled else 'off'}")
        return
    if value not in ("on", "off"):
        render.print_error("usage: /nyx [on|off]")
        return
    orchestrator.set_nyx(value == "on")
    render.print_info(f"nyx → {value}")


def _handle_workflow(orchestrator: Orchestrator, arg: str) -> str | None:
    """Handles /workflow <run|save|show|delete> ...

    Returns "workflow-run:<name>" for /workflow run (the caller — ui.app's
    async turn loop — is the only thing that can actually execute a
    workflow's steps, since that requires awaiting each step's turn); returns
    None for every other subcommand (handled fully here).
    """
    parts = arg.split(None, 1)
    if not parts:
        render.print_error("usage: /workflow <run|save|show|delete> <name> ...")
        return None
    sub, rest = parts[0], (parts[1] if len(parts) > 1 else "").strip()

    if sub == "run":
        if not rest:
            render.print_error("usage: /workflow run <name>")
        elif orchestrator.workflow_store.get(rest) is None:
            render.print_error(f"no such workflow: {rest}")
        else:
            return f"workflow-run:{rest}"
        return None

    if sub == "show":
        wf = orchestrator.workflow_store.get(rest) if rest else None
        if wf is None:
            render.print_error(f"no such workflow: {rest or '(missing name)'}")
        else:
            render.print_workflow_steps(wf)
        return None

    if sub == "save":
        save_parts = rest.split(None, 1)
        if not save_parts:
            render.print_error("usage: /workflow save <name> [n]  (n = last n user turns, default 5)")
            return None
        name = save_parts[0]
        count_str = save_parts[1].strip() if len(save_parts) > 1 else ""
        n = int(count_str) if count_str.isdigit() else 5
        if orchestrator.state is None or not orchestrator.state.messages:
            render.print_error("no turns to save yet")
            return None
        steps = [m.content for m in orchestrator.state.messages if m.role == "user"][-n:]
        if not steps:
            render.print_error("no user turns to save yet")
            return None
        orchestrator.workflow_store.save(Workflow(name=name, steps=steps, description=f"last {len(steps)} turn(s)"))
        render.print_info(f"saved workflow '{name}' ({len(steps)} steps)")
        return None

    if sub == "delete":
        if not rest:
            render.print_error("usage: /workflow delete <name>")
        elif orchestrator.workflow_store.delete(rest):
            render.print_info(f"deleted workflow '{rest}'")
        else:
            render.print_error(f"no such workflow: {rest}")
        return None

    render.print_error(f"unknown /workflow subcommand: {sub} (try run|save|show|delete)")
    return None


_BUILTIN_PROVIDER_NAMES = ("stub", "anthropic")


def _providers_store(orchestrator: Orchestrator) -> ProviderStore:
    root = orchestrator.config.storage_root or (Path.home() / ".reidcli")
    return ProviderStore(root)


def _handle_providers(orchestrator: Orchestrator) -> None:
    store = _providers_store(orchestrator)
    persisted = store.list()
    persisted_names = {r.name for r in persisted}
    active = orchestrator.state.session.provider if orchestrator.state else orchestrator.config.default_provider
    extra: list[str] = []
    if orchestrator.providers is not None:
        for name in orchestrator.providers.names():
            if name not in persisted_names:
                extra.append(name)
    render.print_providers(persisted, active, extra)


def _handle_connect(orchestrator: Orchestrator, arg: str) -> None:
    parts = arg.split()
    if len(parts) < 3:
        render.print_error(
            "usage: /connect <name> <kind> <base_url> [api_key] [model]  "
            f"(kind: {'|'.join(SUPPORTED_KINDS)})"
        )
        return
    name, kind, base_url = parts[0], parts[1], parts[2]
    if kind not in SUPPORTED_KINDS:
        render.print_error(f"unknown kind: {kind} (try {'|'.join(SUPPORTED_KINDS)})")
        return
    if name in _BUILTIN_PROVIDER_NAMES and kind != "anthropic":
        render.print_error(f"name '{name}' is reserved for the built-in provider")
        return
    api_key = parts[3] if len(parts) > 3 else ""
    model = parts[4] if len(parts) > 4 else ""
    record = ProviderRecord(name=name, kind=kind, base_url=base_url, api_key=api_key, default_model=model)
    try:
        provider = build_provider(record)
    except ValueError as exc:
        render.print_error(f"failed to build provider: {exc}")
        return
    _providers_store(orchestrator).save(record)
    if orchestrator.providers is not None:
        orchestrator.providers.register(name, provider)
    render.print_info(f"connected provider '{name}' ({kind}) → {base_url or '(default)'}")
    render.print_info(f"switch with: /use {name}")


def _handle_disconnect(orchestrator: Orchestrator, arg: str) -> None:
    name = arg.strip()
    if not name:
        render.print_error("usage: /disconnect <name>")
        return
    if name in _BUILTIN_PROVIDER_NAMES:
        render.print_error(f"cannot disconnect built-in provider '{name}'")
        return
    active = orchestrator.state.session.provider if orchestrator.state else ""
    if name == active:
        render.print_error(f"'{name}' is active; /use stub first, then disconnect")
        return
    removed = _providers_store(orchestrator).delete(name)
    if orchestrator.providers is not None:
        orchestrator.providers.unregister(name)
    if removed:
        render.print_info(f"disconnected '{name}'")
    else:
        render.print_error(f"no saved provider named '{name}'")


def _handle_use(orchestrator: Orchestrator, arg: str) -> None:
    name = arg.strip()
    if not name:
        render.print_error("usage: /use <name> (see /providers)")
        return
    if orchestrator.providers is None or not orchestrator.providers.has(name):
        render.print_error(f"provider '{name}' is not registered (see /providers)")
        return
    if orchestrator.state is None:
        render.print_error("no active session")
        return
    try:
        orchestrator.use_provider(name)
    except (KeyError, RuntimeError) as exc:
        render.print_error(str(exc))
        return
    render.print_info(f"active provider → {name}  (model: {orchestrator.state.session.model})")


def handle(orchestrator: Orchestrator, line: str) -> str:
    parts = line.strip().split(None, 1)
    cmd = parts[0].lstrip("/")
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("help", "?"):
        render.console.print(HELP)
    elif cmd == "status":
        if orchestrator.state:
            chars = sum(len(m.content or "") for m in orchestrator.state.messages)
            render.status_bar(
                orchestrator.state.session,
                orchestrator.state.effective_mode,
                len(orchestrator.list_tasks()),
                tokens_used=max(1, chars // 4),
            )
        else:
            render.print_info("no active session")
    elif cmd == "sessions":
        render.print_sessions(orchestrator.session_store.list())
    elif cmd == "resume":
        if not arg:
            render.print_error("usage: /resume <session-id>")
        else:
            try:
                orchestrator.resume_session(arg)
                count = len(orchestrator.state.messages) if orchestrator.state else 0
                render.print_info(f"resumed {arg} ({count} messages restored)")
            except KeyError as exc:
                render.print_error(str(exc))
    elif cmd == "tasks":
        tasks = orchestrator.list_tasks()
        if arg:
            tasks = [t for t in tasks if t.status.value == arg]
        render.print_tasks(tasks)
    elif cmd == "transcript":
        if orchestrator.state is None:
            render.print_info("no active session")
        else:
            n = int(arg) if arg.isdigit() else 20
            render.print_transcript(orchestrator.state.messages, n)
    elif cmd == "model":
        if not arg or orchestrator.state is None:
            render.print_error("usage: /model <name> (with an active session)")
        else:
            orchestrator.state.session.model = arg
            orchestrator.session_store.update(orchestrator.state.session)
            render.print_info(f"model → {arg}")
    elif cmd == "effort":
        if orchestrator.state is None:
            render.print_error("usage: /effort <low|medium|high|xhigh> (with an active session)")
        elif not arg:
            render.print_info(f"current effort: {orchestrator.state.session.reasoning_effort}")
        elif arg not in _EFFORT_LEVELS:
            render.print_error(f"unknown effort: {arg} (try low|medium|high|xhigh)")
        else:
            orchestrator.state.session.reasoning_effort = arg
            orchestrator.session_store.update(orchestrator.state.session)
            render.print_info(f"effort → {arg}")
    elif cmd == "mode":
        if not arg:
            render.print_info(f"current mode: {orchestrator.policy.mode.value}")
        else:
            _set_mode(orchestrator, arg)
    elif cmd == "nyx":
        _handle_nyx(orchestrator, arg)
    elif cmd == "permissions":
        render.print_permissions(orchestrator.policy)
    elif cmd == "tools":
        render.print_tools(orchestrator.tools.definitions())
    elif cmd == "rewind":
        if orchestrator.state is None or not orchestrator.state.messages:
            render.print_info("nothing to rewind")
        else:
            orchestrator.rewind()
            render.print_info(f"rewound to {len(orchestrator.state.messages)} messages")
    elif cmd == "workflows":
        render.print_workflows(orchestrator.workflow_store.list())
    elif cmd == "workflow":
        outcome = _handle_workflow(orchestrator, arg)
        if outcome is not None:
            return outcome
    elif cmd == "providers":
        _handle_providers(orchestrator)
    elif cmd == "connect":
        _handle_connect(orchestrator, arg)
    elif cmd == "disconnect":
        _handle_disconnect(orchestrator, arg)
    elif cmd == "use":
        _handle_use(orchestrator, arg)
    elif cmd == "clear":
        render.console.clear()
    elif cmd in ("exit", "quit", "q"):
        return "exit"
    else:
        render.print_error(f"unknown command: /{cmd} (try /help)")
    return "continue"
