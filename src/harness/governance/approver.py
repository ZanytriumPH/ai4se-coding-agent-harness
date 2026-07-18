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
    """Task 14 充实：通过 WebUI session 与前端交互审批。

    内核外薄层（§A.4）：不参与 mock 单测路径。注入 session 时走
    ``session.ask(action)``（SSE + POST 回传）；否则回落到可注入的 ``ask``
    回调桩（供单元测试用，保持 ``WebApprover(ask=...)`` 契约）。
    """
    def __init__(self, session=None, ask=None):
        self._session = session
        self._ask = ask

    def approve(self, action: Action) -> bool:
        if self._session is not None:
            return self._session.ask(action)
        return (self._ask or (lambda _a: False))(action)