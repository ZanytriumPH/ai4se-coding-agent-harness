# src/harness/governance/approver.py
from __future__ import annotations
from typing import Protocol
from harness.models import Action


class Approver(Protocol):
    def approve(self, action: Action) -> bool: ...


class AutoRejectApprover:
    def approve(self, action: Action) -> bool:
        return False


class CliApprover:
    def __init__(self, input_fn=input, print_fn=print):
        self._input = input_fn
        self._print = print_fn

    def approve(self, action: Action) -> bool:
        self._print(f"[HITL] approve action? {action.tool} {action.args} [y/N]")
        return self._input().strip().lower() == "y"


class WebApprover:
    """Task 14 充实：通过 SSE/POST 与前端交互。此处留可注入的回调桩。"""
    def __init__(self, ask=None):
        self._ask = ask or (lambda _a: False)

    def approve(self, action: Action) -> bool:
        return self._ask(action)