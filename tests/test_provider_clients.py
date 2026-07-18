# tests/test_provider_clients.py
import httpx
from harness.llm.deepseek import DeepSeekClient
from harness.llm.anthropic_client import AnthropicClient


def _client(cls, payload, status=200):
    transport = httpx.MockTransport(lambda req: httpx.Response(status, json=payload))
    return cls(api_key="sk-test", http_client=httpx.Client(transport=transport))


def test_deepseek_parses_tool_call():
    payload = {"choices": [{"message": {"content": None, "tool_calls": [
        {"id": "1", "type": "function",
         "function": {"name": "write_file",
                      "arguments": '{"path": "a.py", "content": "x"}'}}]}}]}
    r = _client(DeepSeekClient, payload).complete([{"role": "user", "content": "fix"}], [])
    assert r.tool == "write_file"
    assert r.args == {"path": "a.py", "content": "x"}
    assert r.parse_error is False


def test_deepseek_parse_error_on_malformed_args():
    payload = {"choices": [{"message": {"tool_calls": [
        {"function": {"name": "write_file", "arguments": "NOT JSON"}}]}}]}
    r = _client(DeepSeekClient, payload).complete([], [])
    assert r.parse_error is True and r.tool is None


def test_deepseek_text_only():
    payload = {"choices": [{"message": {"content": "thinking..."}}]}
    r = _client(DeepSeekClient, payload).complete([], [])
    assert r.tool is None and r.text == "thinking..."


def test_anthropic_parses_tool_use():
    payload = {"content": [{"type": "tool_use", "id": "1", "name": "run_tests", "input": {}}]}
    r = _client(AnthropicClient, payload).complete([{"role": "user", "content": "fix"}], [])
    assert r.tool == "run_tests" and r.args == {}


def test_anthropic_text_only():
    payload = {"content": [{"type": "text", "text": "thinking..."}]}
    r = _client(AnthropicClient, payload).complete([], [])
    assert r.tool is None and r.text == "thinking..."


def test_anthropic_parse_error_on_empty_content():
    r = _client(AnthropicClient, {"content": []}).complete([], [])
    assert r.parse_error is True