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


class RecordingLLM:
    """Records the tools_schema handed to complete() each call."""
    def __init__(self):
        self.seen_schemas = []
        self._n = 0
    def complete(self, messages, tools_schema):
        self.seen_schemas.append(tools_schema)
        self._n += 1
        return LLMResponse(tool=None, args=None, text="stop")  # → incomplete, 1 call


class LoopingLLM:
    """Always calls read_file — simulates a stuck real LLM that never reaches
    a validator tool. Used to prove the hard turn cap bounds non-validator loops."""
    def __init__(self):
        self.calls = 0
    def complete(self, messages, tools_schema):
        self.calls += 1
        return LLMResponse(tool="read_file", args={"path": "src/app.py"}, text=None)


def test_loop_hard_turn_cap_bounds_non_validator_loop(tmp_path):
    llm = LoopingLLM()
    loop = AgentLoop(
        llm=llm,
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=4, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "max_rounds", f"expected max_rounds got {result.outcome}"
    assert llm.calls == 4, f"cap should bound LLM calls to max_rounds=4, got {llm.calls}"
    assert len(result.turn_records) <= 4


class ProtocolRecordingLLM:
    """Returns a scripted tool_call with an id; captures the messages it sees."""
    def __init__(self):
        self.seen = []
        self._n = 0
    def complete(self, messages, tools_schema):
        # snapshot (dicts are mutated in place by the caller)
        self.seen.append([dict(m) for m in messages])
        self._n += 1
        if self._n == 1:
            return LLMResponse(tool="run_tests", args={}, text=None, tool_call_id="call_1")
        return LLMResponse(tool=None, args=None, text="done")


def test_loop_builds_tool_use_protocol_messages(tmp_path):
    # Real OpenAI-style LLMs require: assistant{tool_calls:[{id,name,arguments}]}
    # then tool{tool_call_id, content}. The old code fed results as `user` messages
    # and never echoed the assistant tool_call → DeepSeek couldn't sustain the
    # dialog and looped (300x read_file). Pin the protocol shape + id pairing.
    llm = ProtocolRecordingLLM()
    loop = AgentLoop(
        llm=llm,
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    loop.run()
    assert len(llm.seen) >= 2, "loop should call the LLM at least twice"
    msgs2 = llm.seen[1]
    roles = [m["role"] for m in msgs2]
    assert "assistant" in roles and "tool" in roles, \
        f"expected assistant+tool roles in 2nd-call messages, got {roles}"
    asst = next(m for m in msgs2 if m["role"] == "assistant" and m.get("tool_calls"))
    toolmsg = next(m for m in msgs2 if m["role"] == "tool")
    tc = asst["tool_calls"][0]
    assert tc["id"] == "call_1" and tc["function"]["name"] == "run_tests"
    assert toolmsg["tool_call_id"] == "call_1", "tool result must pair with the call id"


def test_loop_forwards_tools_schema_to_llm(tmp_path):
    # A real run feeds the LLM the tool defs so it knows what to call. The loop
    # must pass tools_schema straight through, not silently drop it.
    schema = [{"type": "function", "function": {"name": "read_file"}}]
    rec = RecordingLLM()
    loop = AgentLoop(
        llm=rec,
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
        tools_schema=schema,
    )
    loop.run()
    assert rec.seen_schemas, "loop never called the LLM"
    assert all(s is schema or s == schema for s in rec.seen_schemas)


def test_loop_default_tools_schema_is_empty(tmp_path):
    # Mock demo path: tools_schema omitted → defaults to [] (no tool defs fed).
    rec = RecordingLLM()
    loop = AgentLoop(
        llm=rec,
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    loop.run()
    assert all(s == [] for s in rec.seen_schemas)


def test_loop_on_turn_fires_once_per_turn(tmp_path):
    # A real-run entry passes on_turn to show live progress. The callback must
    # fire exactly once per finalized turn, with 1-based round numbers.
    script = [
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "bad"}, text=None),
        LLMResponse(tool="run_tests", args={}, text=None),
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "good"}, text=None),
        LLMResponse(tool="run_tests", args={}, text=None),
    ]
    seen = []
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
        on_turn=seen.append,
    )
    result = loop.run()
    assert result.outcome == "success"
    assert [t.round for t in seen] == [1, 2, 3, 4]
    # turn 2 (run_tests, fail) must carry feedback; turn 1 (write_file) must not
    assert seen[1].feedback is not None and seen[1].feedback.verdict.value == "fail"
    assert seen[0].feedback is None
