# tests/test_loop.py
from harness.loop import AgentLoop
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.governance.guardrail import Guardrail, Decision
from harness.governance.approver import AutoRejectApprover
from harness.config import GuardrailRules, ValidatorConfig
from harness.feedback.feedback_loop import FeedbackLoop
from harness.feedback.validators import PytestValidator, Product
from harness.tools.dispatcher import ToolDispatcher
from harness.memory.memory import Memory
from harness.models import Action
import json, types

class StubDispatcher:
    """对 write_file 不真写, 对 run_tests 返回预设产物, 让测试无网络/无 pytest。"""
    def __init__(self, fail_then_pass):
        self.calls = 0
        self.fail_then_pass = fail_then_pass
    def exec(self, action: Action):
        if action.tool == "run_tests":
            self.calls += 1
            report = {"summary": {"passed": 0, "failed": 1, "errors": 0},
                      "tests": [{"nodeid": "t::x", "outcome": "failed",
                                 "call": {"crash": {"type": "AssertionError", "message": "m"}}}]} if self.calls < 2 else {"summary": {"passed": 1, "failed": 0, "errors": 0}, "tests": []}
            return Product(1, json.dumps(report), "")
        return Product(0, "", "")

def test_loop_recovers_from_fail_to_success(tmp_path):
    # MockLLM: 第1轮写"坏"修复+跑测试→fail; 第2轮写"好"修复+跑测试→pass
    script = [
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "bad"}, text=None),
        LLMResponse(tool="run_tests", args={}, text=None),
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "good"}, text=None),
        LLMResponse(tool="run_tests", args={}, text=None),
    ]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "success"
    assert result.rounds == 2

def test_loop_incomplete_when_llm_gives_no_tool(tmp_path):
    # LLM returns text-only (no tool) → loop must break and report "incomplete",
    # not mislabel it "max_rounds" (which means the round budget was exhausted).
    loop = AgentLoop(
        llm=MockLLMClient([LLMResponse(tool=None, args=None, text="I give up")]),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "incomplete"

def test_loop_records_rejected_audit_for_denied_approval(tmp_path):
    # write to absolute path → NEED_APPROVAL; AutoRejectApprover → rejected.
    # The TurnRecord must record the actual outcome "rejected", not "need_approval".
    script = [LLMResponse(tool="write_file", args={"path": "/etc/passwd", "content": "x"}, text=None)]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    rejected = [t for t in result.turn_records if t.guardrail_decision == "rejected"]
    assert len(rejected) == 1
