"""Agent loop: the core execution cycle.

A single turn:
  1. append user message
  2. call provider with tool schemas
  3. if the provider returns tool calls -> dispatch each through the registry
     (policy-gated), append tool-result messages, loop back to step 2
  4. if the provider returns a final text stop -> append assistant message, return

The loop is bounded by max_steps to avoid runaway tool cycling. Failures from tools
become tool-result messages with error text so the model can react, never crashes.
"""
from __future__ import annotations

from typing import Any

from reidcli.diagnostics.logger import get_logger
from reidcli.policy.engine import PolicyEngine
from reidcli.provider.base import BaseProvider, Message, ProviderResponse, ToolCall
from reidcli.runtime.reasoning import COT_SYSTEM_SUFFIX, split_reasoning
from reidcli.runtime.state import RuntimeState
from reidcli.tools.base import Approver, ToolContext
from reidcli.tools.registry import ToolRegistry

log = get_logger("reidcli.agent")

MAX_STEPS = 8

BASE_SYSTEM_PROMPT = "You are ReidVerse-Cli, a terminal-native coding agent. Use tools when helpful."


class Agent:
    """Generic tool-calling agent. Role specialization can subclass later."""

    def __init__(
        self,
        provider: BaseProvider,
        tools: ToolRegistry,
        policy: PolicyEngine,
        *,
        system_prompt: str = BASE_SYSTEM_PROMPT + COT_SYSTEM_SUFFIX,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.policy = policy
        self.system_prompt = system_prompt

    def _context(
        self, state: RuntimeState, writable_roots: list, approver: Approver | None
    ) -> ToolContext:
        return ToolContext(
            workspace_root=state.session.workspace,
            policy=self.policy,
            writable_roots=writable_roots,
            approver=approver,
        )

    def _ensure_system(self, state: RuntimeState) -> None:
        if not state.messages or state.messages[0].role != "system":
            state.messages.insert(0, Message(role="system", content=self.system_prompt))

    def run_turn(
        self,
        state: RuntimeState,
        user_input: str,
        *,
        writable_roots: list | None = None,
        approver: Approver | None = None,
        max_steps: int = MAX_STEPS,
    ) -> tuple[str, list[dict]]:
        """Execute one user turn. Returns (final_text, tool_result_log).

        The orchestrator owns the policy mode; this loop only reads it. One assistant
        message is appended per provider turn, carrying both content and tool_calls.
        """
        self._ensure_system(state)
        state.messages.append(Message(role="user", content=user_input))
        ctx = self._context(state, writable_roots or [], approver)
        tool_log: list[dict] = []
        final_text = ""
        state.last_thinking = None  # fresh per turn; the UI reads it after run_turn

        for _step in range(max_steps):
            resp: ProviderResponse = self.provider.chat(
                state.messages, self.tools.schemas(), state.session.model
            )
            # Separate chain-of-thought from the answer. The reasoning is ephemeral:
            # only the clean answer is stored in the transcript / fed back to the model.
            thinking, answer = split_reasoning(resp.text)
            if thinking:
                state.last_thinking = thinking
            # Single assistant message per turn, carrying both content and tool_calls.
            state.messages.append(
                Message(role="assistant", content=answer, tool_calls=resp.tool_calls)
            )
            if answer:
                final_text = answer

            if not resp.tool_calls:
                break

            for call in resp.tool_calls:
                result = self.tools.dispatch(call.name, call.arguments, ctx)
                tool_log.append(
                    {"name": call.name, "args": call.arguments, "ok": result.ok, "error": result.error}
                )
                state.messages.append(
                    Message(
                        role="tool",
                        content=result.output if result.ok else f"ERROR: {result.error}\n{result.output}",
                        tool_call_id=call.id,
                    )
                )
            state.last_tool_results = tool_log
        else:
            final_text = final_text or "[agent] step budget exhausted without a final answer."

        state.turns += 1
        return final_text, tool_log


# Re-exported for convenience so callers can build agents from config.
def build_agent(provider: BaseProvider, tools: ToolRegistry, policy: PolicyEngine) -> Agent:
    return Agent(provider, tools, policy)


# Silence unused import warnings for re-exports.
__all__ = ["Agent", "build_agent", "ToolCall", "Any"]
