"""Harness CLI entrypoint — the canonical way to run the harness (G1).

Three run modes (after the credential flags):
  harness --workdir <repo>              # terminal HITL run against a real LLM
  harness --run-webui --workdir <repo>  # browser HITL run (serves on --port)
  harness --run-webui --mock            # token-free scripted demo (1 approval)
  harness --headless                    # pointer to the mock three-act demo

Plus credential management: --init-key / --status / --update-key / --clear-key
(通用要求 §3.1 — key never printed, never persisted to git/history/plaintext
config; keyring preferred, .env only as a明文 dev convenience).

demo/run_live.py and demo/run_webui.py are thin wrappers that delegate here
with demo defaults (workdir=demo/target_repo; the webui one injects --run-webui).
The real-run logic lives in ONE place — here — so the two entrypoints can't
drift, and `uvicorn webui.server:app` works for deploy (server.py exposes a
module-level app).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import threading
from pathlib import Path

from harness.config import Config
from harness.credentials import CredentialStore
from harness.prompt import SYSTEM_PROMPT
from harness.governance.guardrail import Guardrail
from harness.governance.approver import CliApprover, WebApprover
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.schema import for_provider
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator, Product
from harness.memory.memory import Memory
from harness.loop import AgentLoop
from harness.llm.deepseek import DeepSeekClient
from harness.llm.anthropic_client import AnthropicClient
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.models import Action


def _load_env(path: str = ".env") -> int:
    """Load KEY=VALUE lines from a .env file into os.environ.

    Skips blank lines and `#` comments. Does NOT override existing env vars.
    Returns the number of variables loaded. No external dependency.

    §3.1 threat-model note: a `.env` file is明文 on disk and visible to the
    process environment — strictly weaker than the OS keyring. Prefer
    --init-key for real credentials; `.env` is a convenience source for
    local/dev only.
    """
    p = Path(path)
    if not p.is_file():
        return 0
    n = 0
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key:
            continue
        if key not in os.environ:
            os.environ[key] = value
            n += 1
    return n


def _get_key(provider: str, from_env: bool) -> str:
    """Fetch the LLM key — never printed, never logged. §3.1."""
    if from_env:
        env_var = "DEEPSEEK_API_KEY" if provider == "deepseek" else "ANTHROPIC_API_KEY"
        key = os.environ.get(env_var)
        if not key:
            sys.exit(f"harness: --from-env set but {env_var} is empty")
        return key
    key = CredentialStore().get()
    if not key:
        sys.exit("harness: no key in keyring — run `harness --init-key` first")
    return key


def _truncate(s: object, limit: int = 200) -> str:
    t = str(s)
    return t if len(t) <= limit else t[:limit] + f" …(+{len(t)-limit} chars)"


def _build_client(provider: str, key: str):
    if provider == "deepseek":
        return DeepSeekClient(api_key=key)
    return AnthropicClient(api_key=key)


def _live_printer(turn) -> None:
    """Per-turn live progress so the operator sees the loop is alive, not hung."""
    fb = ""
    if turn.feedback is not None:
        fb = f" verdict={turn.feedback.verdict.value}"
        fb += f" failures={len(turn.feedback.failures)}"
    print(f"  [turn {turn.round}] {turn.guardrail_decision}  "
          f"{turn.action.tool} {_truncate(turn.action.args, 120)}{fb}", flush=True)


def _turn_to_event(turn) -> str:
    """Format a TurnRecord as a single SSE line for the browser log."""
    fb = ""
    if turn.feedback is not None:
        fb = f" verdict={turn.feedback.verdict.value}"
        fb += f" failures={len(turn.feedback.failures)}"
    return (f"[turn {turn.round}] {turn.guardrail_decision}  "
            f"{turn.action.tool} {_truncate(turn.action.args, 120)}{fb}")


def _print_audit(result) -> None:
    print("\n=== RUN RESULT ===")
    print(f"outcome = {result.outcome}   rounds = {result.rounds}")
    print(f"--- per-turn audit ({len(result.turn_records)} turns) ---")
    for t in result.turn_records:
        fb = ""
        if t.feedback is not None:
            fb = f" verdict={t.feedback.verdict.value}" if t.feedback.verdict else ""
            fails = len(t.feedback.failures)
            fb += f" failures={fails}"
        print(f"  turn {t.round}: {t.guardrail_decision}  "
              f"{t.action.tool} {_truncate(t.action.args)}{fb}")
    print("(key never printed; args truncated to 200 chars)")


def _build_loop(client, cfg, workdir, approver, on_turn, provider) -> AgentLoop:
    """Assemble the AgentLoop for a real (terminal or webui) run.

    Single wiring point so terminal-HITL and browser-HITL can't drift: both
    inject their own approver + on_turn; the rest (validators, guardrail,
    memory, system_prompt, 6-tool schema) is identical.
    """
    return AgentLoop(
        llm=client,
        guardrail=Guardrail(cfg.guardrail),
        approver=approver,
        dispatcher=ToolDispatcher(workdir),
        validators={"test": PytestValidator(), "lint": RuffValidator(),
                    "type": MypyValidator()},
        feedback_cfg=cfg.validator,
        memory=Memory(str(Path(cfg.memory_path))),
        system_prompt=SYSTEM_PROMPT,
        tools_schema=for_provider(provider),
        on_turn=on_turn,
    )


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


def _build_mock_loop(session, cfg, tmp_path) -> AgentLoop:
    """Token-free webui demo: run_tests(fail) -> write_file(ABS path =>
    NEED_APPROVAL => browser) -> run_tests(pass). The absolute path trips the
    guardrail's escape check, so WebApprover blocks on session.ask() and the
    approval card shows in the UI. Mirrors demo/run_webui --mock."""
    script = [
        LLMResponse("run_tests", {}, None),
        LLMResponse("write_file", {"path": "/etc/guarded.py", "content": "x = 1"}, None),
        LLMResponse("run_tests", {}, None),
    ]
    return AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(cfg.guardrail),
        approver=WebApprover(session=session),
        dispatcher=_MockDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=cfg.validator,
        memory=Memory(str(tmp_path / "mem.jsonl")),
        system_prompt=SYSTEM_PROMPT,
        tools_schema=[],  # mock LLM ignores schema
        on_turn=lambda t: session.push(_turn_to_event(t)),
    )


def _run_terminal(args, cfg, client, provider) -> int:
    approver = (lambda _: True) if args.yes else CliApprover()
    loop = _build_loop(client, cfg, args.workdir, approver, _live_printer, provider)
    print(f"harness: provider={provider} workdir={args.workdir} "
          f"max_rounds={cfg.validator.max_rounds} "
          f"hitl={'off(--yes)' if args.yes else 'on'}")
    print("harness: starting loop (this makes REAL LLM calls — costs tokens)…")
    result = loop.run()
    _print_audit(result)
    return 0 if result.outcome == "success" else 1


def _run_webui(args, cfg) -> int:
    import uvicorn  # lazy so --help / --headless work without starlette/uvicorn
    from webui.server import make_app, WebUISession

    session = WebUISession()
    app = make_app(session)
    server = threading.Thread(
        target=uvicorn.run, args=(app,),
        kwargs={"host": args.host, "port": args.port, "log_level": "warning"},
        daemon=True)
    server.start()
    url = f"http://localhost:{args.port}"
    print(f"harness: webui serving on {url}  (open it in a browser)")

    if args.mock:
        print("harness: --mock mode (token-free): watch the log, approve the "
              "guarded write_file when the card pops up. Replays forever — the "
              "process never exits, so the platform never restarts the replica "
              "(an exit → restart → cold-start 502 'connection dial timeout').")
        import tempfile
        tmp = Path(tempfile.gettempdir())
        # Replay the mock loop forever. The loop blocks at the turn-2 approval
        # until a visitor clicks Approve, so this is NOT a busy loop — it parks
        # waiting for HITL, completes one 3-act run, then immediately re-runs
        # (turn 1 → approval card → …). uvicorn (started above) stays up across
        # replays; the process never exits, so no restart, no 502.
        while True:
            loop = _build_mock_loop(session, cfg, tmp)
            try:
                result = loop.run()
            except KeyboardInterrupt:
                print("\nharness: interrupted by user")
                return 130
            summary = (f"=== RUN RESULT === outcome={result.outcome} "
                       f"rounds={result.rounds} "
                       f"({len(result.turn_records)} turns; replaying the demo…)")
            print(summary)
            session.push(summary)

    # real-LLM run-once path (local operator use; exits after 30s)
    provider = args.provider or cfg.llm_provider
    print(f"harness: provider={provider} workdir={args.workdir} "
          f"max_rounds={cfg.validator.max_rounds} (REAL LLM — costs tokens)")
    client = _build_client(provider, _get_key(provider, args.from_env))
    loop = _build_loop(client, cfg, args.workdir,
                       WebApprover(session=session),
                       lambda t: session.push(_turn_to_event(t)), provider)
    print("harness: starting agent loop… (Ctrl+C to stop)")
    try:
        result = loop.run()
    except KeyboardInterrupt:
        print("\nharness: interrupted by user")
        return 130
    summary = (f"\n=== RUN RESULT ===\noutcome = {result.outcome}   "
               f"rounds = {result.rounds}\n"
               f"({len(result.turn_records)} turns; see browser log)")
    print(summary)
    session.push(summary.strip())
    print(f"harness: loop done; server still up at {url} for 30s — view the log.")
    threading.Event().wait(30)
    return 0 if result.outcome == "success" else 1


def main(argv=None):
    _load_env(".env")

    p = argparse.ArgumentParser(prog="harness")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--workdir", default=".",
                   help="repo the agent repairs (terminal + real-webui modes)")
    p.add_argument("--headless", action="store_true",
                   help="keyless pointer to the mock three-act mechanism demo")
    p.add_argument("--run-webui", action="store_true",
                   help="browser HITL: serve the webui and drive the loop")
    p.add_argument("--mock", action="store_true",
                   help="(with --run-webui) token-free scripted demo, 1 approval")
    p.add_argument("--provider", choices=["deepseek", "anthropic"], default=None,
                   help="override config.yaml llm_provider")
    p.add_argument("--from-env", action="store_true",
                   help="read key from env instead of keyring")
    p.add_argument("--yes", action="store_true",
                   help="auto-approve every HITL action (terminal mode; unattended)")
    p.add_argument("--max-rounds", type=int, default=None,
                   help="override config.yaml validator.max_rounds")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1")
    # credential management (§3.1)
    p.add_argument("--init-key", action="store_true",
                   help="guide first-time key entry (hidden input)")
    p.add_argument("--status", action="store_true",
                   help="print key status (never the plaintext key)")
    p.add_argument("--update-key", action="store_true",
                   help="update the stored key (hidden entry, overwrites)")
    p.add_argument("--clear-key", action="store_true",
                   help="clear the stored key, then print status")
    args = p.parse_args(argv)

    # --- credential management: short-circuit before any run path ---
    if args.init_key:
        cs = CredentialStore()
        cs.store(getpass.getpass("Enter LLM API key (hidden): "))
        print("status:", cs.status())
        return 0

    if args.status:
        print(CredentialStore().status())
        return 0

    if args.update_key:
        cs = CredentialStore()
        cs.update(getpass.getpass("Enter new LLM API key (hidden): "))
        print("status:", cs.status())
        return 0

    if args.clear_key:
        cs = CredentialStore()
        cs.clear()
        print("status:", cs.status())
        return 0

    # --- run paths ---
    cfg = Config.load(args.config)
    if args.max_rounds is not None:
        cfg.validator.max_rounds = args.max_rounds

    if args.headless:
        # Keyless escape hatch: the three-act mechanism demo runs under a mock
        # LLM, no key needed. See demo/run_demo.py.
        print("headless: run `python -m demo.run_demo` for the token-free "
              "three-act mechanism demo (guardrail deny → feedback fix → "
              "no-progress stop). No LLM key required.")
        return 0

    if args.run_webui:
        return _run_webui(args, cfg)

    # default: terminal HITL run against a real LLM
    provider = args.provider or cfg.llm_provider
    client = _build_client(provider, _get_key(provider, args.from_env))
    return _run_terminal(args, cfg, client, provider)


if __name__ == "__main__":
    sys.exit(main())
