# demo/run_webui.py
"""Launch the WebUI driving a REAL harness repair with browser HITL.

Closes the PR-4 gap: `make_app(session)` + frontend protocol (SSE /events,
GET /pending, POST /approve) were all wired, but nothing drove an AgentLoop
against the session. This launcher:

  - creates a WebUISession and serves make_app(session) via uvicorn (bg thread)
  - runs an AgentLoop in the main thread with:
      * WebApprover(session)  — NEED_APPROVAL actions block on session.ask(),
        surfacing in the browser for Approve/Reject (the HITL roundtrip)
      * on_turn -> session.push(...)  — each turn streams to the browser log
  - reuses the PR-6 real-run wiring (tools_schema, python -m pytest, system_prompt)

So you open http://localhost:8000, watch the agent work live in the log, and
when it tries a guarded action the approval card pops up — you click, the loop
resumes. That's the WebUI end-to-end, locally, before deploying.

Credential hygiene (§3.1): key from keyring (never printed); --from-env fallback.
Usage (from worktree root, after `pip install -e ".[llm,dev]"` + `harness --init-key`):
    python -m demo.run_live ...        # compare: terminal HITL
    python -m demo.run_webui           # browser HITL, real DeepSeek
    python -m demo.run_webui --mock     # token-free scripted demo (triggers 1 approval)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

from harness.config import Config
from harness.credentials import CredentialStore
from harness.governance.guardrail import Guardrail
from harness.governance.approver import WebApprover
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.schema import for_provider
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator
from harness.memory.memory import Memory
from harness.loop import AgentLoop
from harness.llm.deepseek import DeepSeekClient
from harness.llm.anthropic_client import AnthropicClient
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.models import Action
from harness.feedback.validators import PytestValidator as _PV
from harness.feedback.validators import Product
from webui.server import make_app, WebUISession

# reuse the PR-6 system prompt + key loader + truncation from run_live
from demo.run_live import SYSTEM_PROMPT, _get_key, _truncate


def _turn_to_event(turn) -> str:
    """Format a TurnRecord as a single SSE line for the browser log."""
    fb = ""
    if turn.feedback is not None:
        fb = f" verdict={turn.feedback.verdict.value}"
        fb += f" failures={len(turn.feedback.failures)}"
    return (f"[turn {turn.round}] {turn.guardrail_decision}  "
            f"{turn.action.tool} {_truncate(turn.action.args, 120)}{fb}")


class _MockDispatcher:
    """Token-free stub for --mock: run_tests returns fail-then-pass, else empty.
    Does not really write files (the approval is about the guardrail decision)."""
    def __init__(self):
        self.calls = 0
    def exec(self, action: Action):
        if action.tool == "run_tests":
            self.calls += 1
            if self.calls == 1:
                rep = {"tests": [{"nodeid": "t::x", "outcome": "failed",
                                  "call": {"crash": {"type": "AssertionError",
                                                      "message": "m"}}}]}
            else:
                rep = {"tests": []}
            return Product(1 if self.calls == 1 else 0, json.dumps(rep), "")
        return Product(0, "", "")


def _build_mock_loop(session, tmp_path):
    # Script: run_tests(fail) -> write_file(ABS path => NEED_APPROVAL => browser)
    # -> run_tests(pass). The absolute path trips the guardrail's escape check,
    # so WebApprover blocks on session.ask() and the approval card shows in UI.
    script = [
        LLMResponse("run_tests", {}, None),
        LLMResponse("write_file", {"path": "/etc/guarded.py", "content": "x = 1"}, None),
        LLMResponse("run_tests", {}, None),
    ]
    return AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(Config.load("config.yaml").guardrail),
        approver=WebApprover(session=session),
        dispatcher=_MockDispatcher(),
        validators={"test": _PV()},
        feedback_cfg=Config.load("config.yaml").validator,
        memory=Memory(str(tmp_path / "mem.jsonl")),
        system_prompt=SYSTEM_PROMPT,
        tools_schema=[],  # mock LLM ignores schema
        on_turn=lambda t: session.push(_turn_to_event(t)),
    )


def _build_real_loop(session, cfg, provider, workdir, from_env):
    key = _get_key(provider, from_env)
    client = DeepSeekClient(api_key=key) if provider == "deepseek" \
        else AnthropicClient(api_key=key)
    return AgentLoop(
        llm=client,
        guardrail=Guardrail(cfg.guardrail),
        approver=WebApprover(session=session),
        dispatcher=ToolDispatcher(workdir),
        validators={"test": PytestValidator(), "lint": RuffValidator(),
                    "type": MypyValidator()},
        feedback_cfg=cfg.validator,
        memory=Memory(str(Path(cfg.memory_path))),
        system_prompt=SYSTEM_PROMPT,
        tools_schema=for_provider(provider),
        on_turn=lambda t: session.push(_turn_to_event(t)),
    )


def main(argv=None) -> int:
    import uvicorn  # imported lazily so --help works without starlette/uvicorn

    p = argparse.ArgumentParser(prog="run_webui")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--provider", choices=["deepseek", "anthropic"], default=None)
    p.add_argument("--workdir", default=str(Path(__file__).resolve().parent / "target_repo"))
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--from-env", action="store_true")
    p.add_argument("--mock", action="store_true",
                   help="token-free scripted demo (triggers 1 browser approval)")
    p.add_argument("--max-rounds", type=int, default=None)
    args = p.parse_args(argv)

    cfg = Config.load(args.config)
    if args.max_rounds is not None:
        cfg.validator.max_rounds = args.max_rounds

    session = WebUISession()
    app = make_app(session)

    # serve the webui in a background thread; the loop runs in main and blocks
    # on session.ask() when a guarded action needs approval.
    server = threading.Thread(
        target=uvicorn.run, args=(app,),
        kwargs={"host": args.host, "port": args.port, "log_level": "warning"},
        daemon=True)
    server.start()

    url = f"http://localhost:{args.port}"
    print(f"run_webui: serving on {url}  (open it in a browser)")
    if args.mock:
        print("run_webui: --mock mode (token-free): watch the log, approve the "
              "guarded write_file when the card pops up.")
        import tempfile, pathlib
        loop = _build_mock_loop(session, pathlib.Path(tempfile.gettempdir()))
    else:
        provider = args.provider or cfg.llm_provider
        print(f"run_webui: provider={provider} workdir={args.workdir} "
              f"max_rounds={cfg.validator.max_rounds} (REAL LLM calls — costs tokens)")
        loop = _build_real_loop(session, cfg, provider, args.workdir, args.from_env)

    print("run_webui: starting agent loop… (Ctrl+C to stop)")
    try:
        result = loop.run()
    except KeyboardInterrupt:
        print("\nrun_webui: interrupted by user")
        return 130

    summary = (f"\n=== RUN RESULT ===\noutcome = {result.outcome}   "
               f"rounds = {result.rounds}\n"
               f"({len(result.turn_records)} turns; see browser log)")
    print(summary)
    session.push(summary.strip())
    # keep the server up briefly so the final result is visible in the browser
    print(f"run_webui: loop done; server still up at {url} for 30s — view the log.")
    threading.Event().wait(30)
    return 0 if result.outcome == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
