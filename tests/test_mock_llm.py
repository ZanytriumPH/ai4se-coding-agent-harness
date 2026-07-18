# tests/test_mock_llm.py
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse

def test_mock_llm_replays_scripted_actions():
    script = [
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "bad"}, text=None, parse_error=False),
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "good"}, text=None, parse_error=False),
    ]
    llm = MockLLMClient(script)
    r1 = llm.complete(messages=[], tools_schema=[])
    r2 = llm.complete(messages=[], tools_schema=[])
    assert r1.tool == "write_file" and r1.args["content"] == "bad"
    assert r2.args["content"] == "good"

def test_mock_llm_exhausts_script_returns_parse_error():
    llm = MockLLMClient([])
    r = llm.complete([], [])
    assert r.parse_error is True and r.tool is None