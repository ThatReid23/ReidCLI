"""Interactive REPL.

Persistent Claude-Code-style chat bar (prompt_toolkit): a framed input pinned at
the bottom with a status bar beneath it, plus real line editing and history. AI
output scrolls above; the bar re-pins on each turn. During a turn the bar is
replaced by a red thinking spinner. Slash commands route to ui.commands.
"""
from __future__ import annotations

from rich.text import Text

from reidcli.diagnostics.logger import get_logger
from reidcli.runtime.orchestrator import Orchestrator
from reidcli.ui import render
from reidcli.ui.commands import handle as handle_command
from reidcli.ui.prompt import ChatBar
from reidcli.ui.theme import WARN

log = get_logger("reidcli.ui")


def _make_approver(status_holder: list):
    """Approval prompt with risk context. Returns True if user allows.

    Pauses the thinking spinner (if one is active) around the interactive read so
    the prompt isn't stomped by the Live display, then resumes it.
    """

    def approve(prompt: str) -> bool:
        status = status_holder[0]
        if status is not None:
            status.stop()
        render.console.print()
        render.console.print(Text(prompt, style=f"bold {WARN}"))
        resp = render.console.input(Text("  allow? [y/N] ", style=WARN)).strip().lower()
        if status is not None:
            status.start()
        return resp in ("y", "yes")

    return approve


def _token_estimator(orchestrator: Orchestrator):
    """Rough live token count from the conversation size (no streaming usage)."""

    def estimate() -> int:
        st = orchestrator.state
        if st is None:
            return 0
        try:
            chars = sum(len(m.content or "") for m in list(st.messages))
        except (RuntimeError, AttributeError):
            return 0
        return max(1, chars // 4)

    return estimate


def _status_fn(orchestrator: Orchestrator):
    """Snapshot for the bottom status bar: (mode, model, task_count)."""

    def status() -> tuple[str, str, int]:
        st = orchestrator.state
        if st is None:
            return ("—", "—", 0)
        return (st.effective_mode.value, st.session.model, len(orchestrator.list_tasks()))

    return status


def repl(orchestrator: Orchestrator) -> int:
    # Reuse an already-resumed session; only start fresh if none is active.
    if orchestrator.state is None:
        orchestrator.start_session(title="interactive")
    render.banner()

    live_holder: list = [None]
    approver = _make_approver(live_holder)
    estimate_tokens = _token_estimator(orchestrator)
    status_fn = _status_fn(orchestrator)
    bar = ChatBar(status_fn)

    while True:
        try:
            line = bar.ask()
        except KeyboardInterrupt:
            continue  # Ctrl+C clears the current line, like Claude Code
        except EOFError:
            render.console.print(Text("bye.", style="dim"))
            return 0

        if not line.strip():
            continue
        # The input box erased on Enter; echo what was submitted so it stays visible.
        render.print_user(line)
        if line.startswith("/"):
            if handle_command(orchestrator, line) == "exit":
                render.console.print(Text("bye.", style="dim"))
                return 0
            continue

        # Keep a box pinned at the bottom while the agent works; its reply prints
        # above it. The box is erased when the turn ends (the input bar takes over).
        try:
            live = render.thinking_box(estimate_tokens, status_fn)
            live_holder[0] = live
            with live:
                result = orchestrator.submit_task(line, approver=approver)
                render.print_thinking(result.get("thinking") or "")
                render.print_tool_calls(result["tools"])
                render.print_assistant(result["text"])
        except Exception as exc:  # noqa: BLE001 - REPL must not die on runtime errors
            render.print_error(str(exc))
            log.exception("turn failed")
            continue
        finally:
            live_holder[0] = None
