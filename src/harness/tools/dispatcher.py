# src/harness/tools/dispatcher.py
from __future__ import annotations
from .base import Tool, Product
from .files import ReadFileTool, WriteFileTool
from .shell import ExecShellTool
from .runners import RunTestsTool, RunLintTool, RunTypecheckTool
from harness.models import Action

class ToolDispatcher:
    def __init__(self, workdir: str):
        self.workdir = workdir
        self.tools: dict[str, Tool] = {
            t.name: t for t in [
                ReadFileTool(), WriteFileTool(), ExecShellTool(),
                RunTestsTool(), RunLintTool(), RunTypecheckTool(),
            ]
        }

    def exec(self, action: Action) -> Product:
        tool = self.tools.get(action.tool)
        if tool is None:
            return Product(1, "", f"unknown tool: {action.tool}")
        return tool.exec(action.args, self.workdir)