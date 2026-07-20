"""Tests for the harness CLI (G1): the canonical run entrypoint.

The real-run path needs a key + live LLM, so it can't be unit-tested directly.
But its WIRING — does _build_loop assemble an AgentLoop with the right client,
approver, system_prompt, and tools_schema? — is deterministic with a mock LLM
and is the part that can drift. Plus the --headless pointer must work keyless.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from harness.cli import main, _build_loop, _build_mock_loop, _MockDispatcher
from harness.config import Config
from harness.governance.approver import CliApprover, WebApprover
from harness.llm.mock import MockLLMClient
from harness.loop import AgentLoop
from webui.server import WebUISession


def test_headless_returns_zero_and_prints_pointer(capsys):
    # --headless is the keyless escape hatch: must NOT need a key, must tell
    # the operator where the token-free mock demo lives.
    rc = main(["--headless"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "demo.run_demo" in out  # the three-act mechanism demo (mock LLM)


def test_build_loop_wires_client_approver_prompt_and_schema(tmp_path):
    # The run path's wiring: cli._build_loop must hand the loop the injected
    # client/approver, the canonical SYSTEM_PROMPT, and the 6-tool schema.
    cfg = Config.load("config.yaml")
    client = MockLLMClient([])  # no calls expected; we only inspect wiring
    seen = []
    loop = _build_loop(
        client, cfg, str(tmp_path),
        approver=CliApprover(input_fn=lambda: "n"),
        on_turn=lambda t: seen.append(t),
        provider="deepseek",
    )
    assert isinstance(loop, AgentLoop)
    assert loop.llm is client                       # injected, not hard-coded
    assert isinstance(loop.approver, CliApprover)
    assert loop.system_prompt and "run_tests" in loop.system_prompt  # canonical prompt
    assert len(loop.tools_schema) == 6              # full tool contract
    assert loop.max_turns == cfg.validator.max_rounds  # hard cap = feedback max


def test_build_loop_anthropic_schema_format(tmp_path):
    cfg = Config.load("config.yaml")
    loop = _build_loop(MockLLMClient([]), cfg, str(tmp_path),
                       approver=CliApprover(input_fn=lambda: "n"),
                       on_turn=None, provider="anthropic")
    # anthropic schema shape: {"name", "description", "input_schema"}
    t = loop.tools_schema[0]
    assert "name" in t and "input_schema" in t


def test_build_mock_loop_uses_web_approver_and_triggers_approval(tmp_path):
    # --mock webui path: the scripted write_file uses an ABSOLUTE path which
    # trips the guardrail → WebApprover blocks on session.ask(). This is the
    # token-free HITL roundtrip demo; it must surface a pending approval.
    cfg = Config.load("config.yaml")
    session = WebUISession()
    loop = _build_mock_loop(session, cfg, Path(str(tmp_path)))
    assert isinstance(loop.approver, WebApprover)
    assert loop.dispatcher.__class__.__name__ == "_MockDispatcher"

    # drive it: ask() parks the guarded action; /pending must see it.
    result = {}
    t = threading.Thread(target=lambda: result.setdefault("r", loop.run()))
    t.start()
    import time
    time.sleep(0.2)
    pending = session.pending_action()
    assert pending is not None and pending.tool == "write_file"
    session.answer(True)   # approve the guarded write
    t.join(timeout=5)
    assert result.get("r") is not None


def test_mock_loop_replays_on_same_session(tmp_path):
    # The public deploy's --mock mode replays the 3-act demo forever on ONE
    # session (uvicorn stays up, the loop re-runs instead of exiting — an exit
    # would make Railway restart the replica and 502 during cold start).
    # Guard: two consecutive _build_mock_loop runs against the SAME session
    # both complete success after an approval (the replay contract the
    # while-loop in _run_webui relies on).
    cfg = Config.load("config.yaml")
    session = WebUISession()

    for i in range(2):
        loop = _build_mock_loop(session, cfg, Path(str(tmp_path)))
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("r", loop.run()))
        t.start()
        import time
        time.sleep(0.2)
        # each replay parks a fresh pending write_file at turn 2
        pending = session.pending_action()
        assert pending is not None and pending.tool == "write_file"
        session.answer(True)
        t.join(timeout=5)
        assert result["r"].outcome == "success", f"replay {i} did not succeed"
