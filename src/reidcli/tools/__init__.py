from reidcli.tools.base import BaseTool, ToolContext, ToolDefinition, ToolResult
from reidcli.tools.file_tools import (
    FindFilesTool,
    GrepFilesTool,
    ListDirTool,
    PatchFileTool,
    ReadFileTool,
    WriteFileTool,
    register_file_tools,
)
from reidcli.tools.registry import ToolRegistry
from reidcli.tools.shell_tool import RunCommandTool, register_shell_tool

__all__ = [
    "BaseTool",
    "FindFilesTool",
    "GrepFilesTool",
    "ListDirTool",
    "PatchFileTool",
    "ReadFileTool",
    "RunCommandTool",
    "ToolContext",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
    "WriteFileTool",
    "register_file_tools",
    "register_shell_tool",
]


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    register_file_tools(reg)
    register_shell_tool(reg)
    return reg
