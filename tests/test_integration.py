# tests/test_integration.py
import json
from pathlib import Path
from harness.loop import AgentLoop
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.governance.guardrail import Guardrail
from harness.governance.approver import AutoRejectApprover
from harness.config import GuardrailRules, ValidatorConfig
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator, Product
from harness.memory.memory import Memory

FIX = Path(__file__).parent / "fixtures"

class RepoDispatcher:
    """模拟对 target_repo 的修复: 第1轮产物=fail, 第2轮=pass。"""
    def __init__(self):
        self.test_calls = 0
    def exec(self, action):
        if action.tool == "run_tests":
            self.test_calls += 1
            if self.test_calls == 1:
                data = json.loads((FIX/"pytest_fail.json").read_text(encoding="utf-8"))
            else:
                data = json.loads((FIX/"pytest_pass.json").read_text(encoding="utf-8"))
            return Product(1 if self.test_calls == 1 else 0, json.dumps(data), "")
        if action.tool == "write_file":
            return Product(0, "wrote", "")
        return Product(0, "", "")

def test_integration_fail_to_success(tmp_path):
    script = [
        LLMResponse("write_file", {"path": "src/app.py", "content": "bad fix"}, None),
        LLMResponse("run_tests", {}, None),
        LLMResponse("write_file", {"path": "src/app.py", "content": "good fix"}, None),
        LLMResponse("run_tests", {}, None),
    ]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=RepoDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "success"
    assert result.rounds == 2