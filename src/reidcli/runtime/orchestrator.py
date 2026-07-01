"""Orchestrator: ties session + tasks + agent into a coherent runtime.

Owns the lifetime of a session's runtime: starting, submitting tasks, resuming,
and persisting transcript/events. The orchestrator is the single place where
session, task, agent, and policy meet — UI and automation layers call into it.
"""
from __future__ import annotations

from pathlib import Path

from reidcli.config.models import Config
from reidcli.diagnostics.logger import get_logger
from reidcli.policy.engine import PolicyEngine
from reidcli.provider.base import BaseProvider
from reidcli.runtime.agent import Agent
from reidcli.runtime.state import RuntimeState
from reidcli.session.models import Session, SessionStatus
from reidcli.session.store import SessionStore
from reidcli.tasks.models import TaskStatus
from reidcli.tasks.store import TaskStore
from reidcli.tools.base import Approver
from reidcli.tools.registry import ToolRegistry

log = get_logger("reidcli.runtime")


class Orchestrator:
    def __init__(
        self,
        config: Config,
        provider: BaseProvider,
        tools: ToolRegistry,
    ) -> None:
        self.config = config
        self.provider = provider
        self.tools = tools
        self.policy = PolicyEngine(config)
        self.session_store = SessionStore(config.storage_root or (Path.home() / ".reidcli"))
        self.agent = Agent(provider, tools, self.policy)
        self.state: RuntimeState | None = None

    def start_session(self, title: str = "") -> Session:
        workspace = (self.config.workspace_root or Path.cwd()).resolve()
        session = Session(
            title=title or "untitled",
            workspace=workspace,
            provider=self.config.default_provider,
            model=self._default_model(),
            permission_mode=self.config.policy.default_mode,
        )
        self.session_store.create(session)
        self.state = RuntimeState(session=session)
        self.session_store.event_log(session.id).write("session_start", {"title": session.title})
        return session

    def _default_model(self) -> str:
        prov = self.config.providers.get(self.config.default_provider)
        return prov.default_model if prov else "stub-v0"

    def resume_session(self, session_id: str) -> Session:
        session = self.session_store.get(session_id)
        if session is None:
            raise KeyError(f"session {session_id} not found")
        self.session_store.set_status(session.id, SessionStatus.ACTIVE)
        self.state = RuntimeState(session=session)
        self.policy.set_mode(session.permission_mode)
        # Restore prior transcript into in-memory state for real continuation.
        self.state.messages = self.session_store.read_messages(session.id)
        self.session_store.event_log(session.id).write("session_resume", {"messages": len(self.state.messages)})
        return session

    def task_store(self) -> TaskStore:
        if self.state is None:
            raise RuntimeError("no active session")
        return TaskStore(self.config.storage_root or (Path.home() / ".reidcli"), self.state.session.id)

    def submit_task(
        self,
        user_input: str,
        *,
        approver: Approver | None = None,
        title: str | None = None,
    ) -> dict:
        """Run one user turn against the agent, tracking it as a Task."""
        if self.state is None:
            raise RuntimeError("no active session; call start_session first")
        store = self.task_store()
        task = store.create(title or user_input[:60])
        store.update_status(task.id, TaskStatus.ACTIVE)
        self.state.active_task_id = task.id

        # Record message count so we can persist only the new messages from this turn.
        pre_turn_count = len(self.state.messages)
        writable_roots = [r.resolve() for r in self.config.policy.additional_writable_roots]
        final_text, tool_log = self.agent.run_turn(
            self.state, user_input, writable_roots=writable_roots, approver=approver
        )

        # Persist new messages incrementally for restorable resume.
        sid = self.state.session.id
        for msg in self.state.messages[pre_turn_count:]:
            self.session_store.append_message(sid, msg)

        # Turn summary in events.jsonl (human-readable, separate from restorable transcript).
        self.session_store.event_log(sid).write(
            "task_complete", {"task_id": task.id, "tools": len(tool_log)}
        )

        # Derive task status from the turn outcome.
        exhausted = final_text.startswith("[agent] step budget exhausted")
        all_tools_failed = bool(tool_log) and not any(entry["ok"] for entry in tool_log)
        if exhausted or all_tools_failed:
            store.update_status(task.id, TaskStatus.FAILED, error=final_text[:200])
        else:
            store.update_status(task.id, TaskStatus.COMPLETED, summary=final_text[:200])
        self.session_store.update(self.state.session)
        return {
            "task_id": task.id,
            "text": final_text,
            "tools": tool_log,
            "thinking": self.state.last_thinking,
        }

    def list_tasks(self) -> list:
        if self.state is None:
            return []
        return self.task_store().list()

    def set_permission_mode(self, mode) -> None:  # type: ignore[no-untyped-def]
        # Single source of truth: update policy engine + session + persist.
        self.policy.set_mode(mode)
        if self.state is None:
            self.config.policy.default_mode = mode
            return
        self.state.session.permission_mode = mode
        self.session_store.update(self.state.session)

    def rewind(self) -> None:
        """Drop messages back to before the last user turn (stub for deeper rewind later)."""
        if self.state is None or not self.state.messages:
            return
        msgs = self.state.messages
        # Find the last user message and drop from there onward.
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].role == "user":
                del msgs[i:]
                break
        # Persist the truncated transcript by rewriting transcript.jsonl.
        sid = self.state.session.id
        path = self.session_store.session_dir(sid) / "transcript.jsonl"
        if path.exists():
            path.write_text(
                "\n".join(m.model_dump_json() for m in msgs) + ("\n" if msgs else ""),
                encoding="utf-8",
            )
        self.session_store.event_log(sid).write("rewind", {"remaining": len(msgs)})
