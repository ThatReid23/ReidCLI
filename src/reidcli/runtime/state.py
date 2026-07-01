"""Runtime state: in-memory state carried across a turn / session.

Holds the active session, the message transcript (mirrored to disk by the
orchestrator), the active task id, and tool-result history. Permission mode lives
on the session and is kept in sync with the policy engine by the orchestrator.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from reidcli.provider.base import Message
from reidcli.session.models import Session


@dataclass
class RuntimeState:
    session: Session
    messages: list[Message] = field(default_factory=list)
    active_task_id: str | None = None
    turns: int = 0
    last_tool_results: list[dict] = field(default_factory=list)
    last_thinking: str | None = None  # chain-of-thought from the last turn (ephemeral)

    @property
    def effective_mode(self):
        return self.session.permission_mode
