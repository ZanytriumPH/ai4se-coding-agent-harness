# demo/run_demo.py
from __future__ import annotations
import json
from harness.governance.guardrail import Guardrail, Decision
from harness.config import GuardrailRules
from harness.models import Action
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.loop import AgentLoop
from harness.governance.approver import AutoRejectApprover
from harness.feedback.validators import PytestValidator, Product
from harness.config import ValidatorConfig
from harness.memory.memory import Memory

def act1_guardrail_denies_destructive():
    g = Guardrail(GuardrailRules(shell_blacklist=["rm -rf"]))
    d = g.inspect(Action("exec_shell", {"cmd": "rm -rf /"}))
    assert d == Decision.DENY, f"expected DENY got {d}"
    print("ACT 1 PASS: guardrail denies rm -rf /")

class FailThenPassDispatcher:
    def __init__(self): self.calls = 0
    def exec(self, action):
        if action.tool == "run_tests":
            self.calls += 1
            if self.calls == 1:
                rep = {"summary": {"passed": 0, "failed": 1, "errors": 0},
                       "tests": [{"nodeid": "t::x", "outcome": "failed",
                                  "call": {"crash": {"type": "AssertionError", "message": "m"}}}]}
            else:
                rep = {"summary": {"passed": 1, "failed": 0, "errors": 0}, "tests": []}
            return Product(1 if self.calls == 1 else 0, json.dumps(rep), "")
        return Product(0, "", "")

def act2_feedback_loop_recovers(tmp_path):
    script = [
        LLMResponse("write_file", {"path": "a.py", "content": "bad"}, None),
        LLMResponse("run_tests", {}, None),
        LLMResponse("write_file", {"path": "a.py", "content": "good"}, None),
        LLMResponse("run_tests", {}, None),
    ]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=FailThenPassDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "success", f"expected success got {result.outcome}"
    print("ACT 2 PASS: feedback loop drives fail->success")

def act3_no_progress_stops(tmp_path):
    # MockLLM 连续输出同一错误修复 → 无进展停机
    script = [LLMResponse("write_file", {"path": "a.py", "content": "bad"}, None),
              LLMResponse("run_tests", {}, None)] * 5
    class StuckDispatcher:
        def exec(self, action):
            if action.tool == "run_tests":
                rep = {"summary": {"passed": 0, "failed": 1, "errors": 0},
                       "tests": [{"nodeid": "t::x", "outcome": "failed",
                                  "call": {"crash": {"type": "AssertionError", "message": "m"}}}]}
                return Product(1, json.dumps(rep), "")
            return Product(0, "", "")
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StuckDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "no_progress", f"expected no_progress got {result.outcome}"
    print("ACT 3 PASS: no-progress stop fires")

if __name__ == "__main__":
    import tempfile
    act1_guardrail_denies_destructive()
    with tempfile.TemporaryDirectory() as td:
        import pathlib
        act2_feedback_loop_recovers(pathlib.Path(td))
        act3_no_progress_stops(pathlib.Path(td))
    print("ALL ACTS PASS")