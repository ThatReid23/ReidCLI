"""Shell tool: controlled command execution.

Gated by the policy engine (command allowlist/denylist + mode). Uses subprocess with
a timeout, captures stdout/stderr, and returns a structured ToolResult. Shell is
treated as HIGH risk by default — in balanced/strict modes the user is prompted.

On Windows, commands run via PowerShell so Unix-only pipes like `head` fail with a
clear message, and common git/pytest invocations work from the workspace cwd.
"""
from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from reidx.policy.models import PermissionDecision, RiskLevel
from reidx.tools.base import BaseTool, ToolContext, ToolDefinition, ToolResult

_PARAMS = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell command to execute."},
        "cwd": {"type": "string", "description": "Working directory. Defaults to workspace root."},
    },
    "required": ["command"],
}

# Unix utilities that often appear in model-generated one-liners but are missing
# on stock Windows (cmd/PowerShell without Git Bash).
_UNIX_ONLY = re.compile(
    r"(?:^|[|&;]\s*|\s)(head|tail|grep|sed|awk|cat|less|more|wc|xargs|tee)\b",
    re.IGNORECASE,
)


def _windows_friendly_command(command: str) -> tuple[str, str | None]:
    """Rewrite or warn about common cross-platform footguns.

    Returns (command, warning_or_none). Warning is prepended to output when set.
    """
    if sys.platform != "win32":
        return command, None
    # `… 2>&1 | head -N` → drop the head pipe (PowerShell has Select-Object -First)
    m = re.search(r"\|\s*head\s+-(\d+)\s*$", command, re.IGNORECASE)
    if m:
        n = m.group(1)
        base = command[: m.start()].rstrip()
        rewritten = f"{base} | Select-Object -First {n}"
        return rewritten, f"rewrote `head -{n}` → Select-Object -First {n} (Windows)"
    m = re.search(r"\|\s*tail\s+-(\d+)\s*$", command, re.IGNORECASE)
    if m:
        n = m.group(1)
        base = command[: m.start()].rstrip()
        rewritten = f"{base} | Select-Object -Last {n}"
        return rewritten, f"rewrote `tail -{n}` → Select-Object -Last {n} (Windows)"
    if _UNIX_ONLY.search(command) and "Select-Object" not in command:
        return command, (
            "note: command uses Unix tools (head/grep/…); on Windows prefer "
            "PowerShell (Select-String, Select-Object) or Git Bash"
        )
    return command, None


class RunCommandTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_command",
            description=(
                "Run a shell command with policy approval and timeout. "
                "On Windows this uses PowerShell. Avoid Unix-only pipes like "
                "`head`/`grep` — use PowerShell equivalents or plain git/pytest."
            ),
            parameters=_PARAMS,
            risk=RiskLevel.HIGH,
        )

    def execute(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult.fail("empty command")
        decision = ctx.policy.check_command(command)
        if decision is PermissionDecision.DENY:
            return ToolResult.fail(f"command blocked by policy: {command}")
        if decision is PermissionDecision.PROMPT:
            if ctx.resolve_decision(f"Run command? `{command}`") is PermissionDecision.DENY:
                return ToolResult.fail("command denied by user")

        command, warn = _windows_friendly_command(command)
        cwd = str(args.get("cwd", "")) or str(ctx.workspace_root)
        timeout = ctx.policy.config.policy.shell_timeout_seconds

        run_kwargs: dict[str, Any] = {
            "shell": True,
            "cwd": cwd,
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "check": False,
            "encoding": "utf-8",
            "errors": "replace",
        }
        # Prefer PowerShell on Windows so `git`/`pytest` and object pipelines work.
        if sys.platform == "win32":
            run_kwargs["executable"] = None
            # -NoProfile speeds startup; -Command runs the string.
            full = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ]
            try:
                proc = subprocess.run(full, **{k: v for k, v in run_kwargs.items() if k != "shell"})
            except FileNotFoundError:
                proc = subprocess.run(command, **run_kwargs)
            except subprocess.TimeoutExpired:
                return ToolResult.fail(f"command timed out after {timeout}s")
            except OSError as exc:
                return ToolResult.fail(f"failed to spawn: {exc}")
        else:
            try:
                proc = subprocess.run(command, **run_kwargs)
            except subprocess.TimeoutExpired:
                return ToolResult.fail(f"command timed out after {timeout}s")
            except OSError as exc:
                return ToolResult.fail(f"failed to spawn: {exc}")

        out = proc.stdout or ""
        if proc.stderr:
            out += ("\n--- stderr ---\n" + proc.stderr) if out else proc.stderr
        if warn:
            out = f"[{warn}]\n{out}" if out else f"[{warn}]"
        ok = proc.returncode == 0
        return ToolResult(
            ok=ok,
            output=out.rstrip(),
            error="" if ok else f"exit code {proc.returncode}",
            data={"exit_code": proc.returncode, "command": command},
        )


def register_shell_tool(registry) -> None:  # type: ignore[no-untyped-def]
    registry.register(RunCommandTool())
