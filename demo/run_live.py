# demo/run_live.py
"""Real end-to-end run: drive the harness with a REAL LLM against demo/target_repo.

This closes REFLECTION 盲点 2 ("真实 LLM 从未端到端跑过"). Wires:

    DeepSeekClient/AnthropicClient  (real API, step-1-verified)
      + ToolDispatcher(workdir=target_repo)        (real subprocess: pytest/ruff/mypy)
      + tools schema  (harness.tools.schema.for_provider — step 2)
      + system_prompt (step 3: workflow + tool contract + 盲点4 discipline)
      + CliApprover   (HITL: every write/exec needs [y/N])
      + Guardrail     (config.yaml deny-lists)
      → AgentLoop.run()  →  prints RunResult + per-turn audit.

Credential hygiene (通用要求 §3.1):
- Key read from the OS keyring via CredentialStore (same path as `harness --init-key`).
- Key is NEVER printed. The per-turn audit prints tool + truncated args, never the key.
- --from-env reads DEEPSEEK_API_KEY/ANTHROPIC_API_KEY for CI convenience (env is明文,
  strictly weaker than keyring — prefer --init-key for real keys).

Usage (from worktree root, after `pip install -e ".[llm,dev]"` + `harness --init-key`):
    python -m demo.run_live                                  # DeepSeek, HITL on
    python -m demo.run_live --provider anthropic
    python -m demo.run_live --yes        # auto-approve all HITL (unattended smoke)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from harness.config import Config
from harness.credentials import CredentialStore
from harness.governance.guardrail import Guardrail
from harness.governance.approver import CliApprover, AutoRejectApprover
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.schema import for_provider
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator
from harness.memory.memory import Memory
from harness.loop import AgentLoop
from harness.llm.deepseek import DeepSeekClient
from harness.llm.anthropic_client import AnthropicClient


# Step 3 — system prompt. Drives real-LLM behaviour (盲点 4: prompt措辞定行为).
# Tuned after observing a DeepSeek-chat real run waste turns on shell path
# debugging and absolute paths: the prompt now mandates run_tests FIRST,
# repo-relative paths, minimal edits, and forbids using exec_shell to debug
# Python import/path issues (the test runner handles paths; a failing test
# means the source logic is wrong, not the environment).
SYSTEM_PROMPT = """\
You are a coding agent repairing a failing Python repository.

STRICT WORKFLOW (follow in order, do not improvise):
1. FIRST action MUST be run_tests — see the failing test nodeids before anything.
   Do NOT explore with shell (find/dir/ls) first; you already know tests live in
   tests/ and source in src/. Do not call exec_shell to list files.
2. read_file ONLY the source file(s) referenced by the failing test nodeids
   (e.g. nodeid tests/test_auth.py::test_login → read tests/test_auth.py and
   src/app.py). Do not read unrelated files.
3. write_file the SMALLEST edit to src that makes the failing assertion pass.
   Never edit or weaken a test. Never delete a test. Do not rewrite the whole
   file — change only the broken function.
4. run_tests again to verify. Iterate 3→4 until run_tests returns no failures.

TOOL CONTRACT — exactly these tools (call one per turn, by name):
- run_tests {}              # pytest over the repo; returns pass/fail + failures
- read_file {path}          # path is REPO-RELATIVE, e.g. "src/app.py"
- write_file {path, content}# path REPO-RELATIVE; overwrite the target file
- run_lint {}               # optional; ruff violations
- run_typecheck {}          # optional; mypy type errors
- exec_shell {cmd}          # AVOID. Only for git status. NEVER use it to debug
                              sys.path / imports / pytest invocation — run_tests
                              already runs pytest correctly; a test failure means
                              the SOURCE is wrong, not the environment.

DISCIPLINE (binding):
- Paths are REPO-RELATIVE ("src/app.py", "tests/test_auth.py"). Never absolute,
  never with "..". Absolute paths are blocked.
- Quote failure messages verbatim from run_tests; never paraphrase or guess.
- If a test failure is genuinely ambiguous, STOP — reply as text describing the
  ambiguity instead of inventing a fix. Do not fabricate tool outputs.
- The only success condition is run_tests returning zero failures. Say nothing
  when done; just keep iterating until run_tests is clean.
"""


def _get_key(provider: str, from_env: bool) -> str:
    if from_env:
        env_var = "DEEPSEEK_API_KEY" if provider == "deepseek" else "ANTHROPIC_API_KEY"
        key = os.environ.get(env_var)
        if not key:
            sys.exit(f"run_live: --from-env set but {env_var} is empty")
        return key
    key = CredentialStore().get()
    if not key:
        sys.exit("run_live: no key in keyring — run `harness --init-key` first")
    return key


def _truncate(s: object, limit: int = 200) -> str:
    t = str(s)
    return t if len(t) <= limit else t[:limit] + f" …(+{len(t)-limit} chars)"


def _live_printer(turn) -> None:
    """Per-turn live progress so the operator sees the loop is alive, not hung."""
    fb = ""
    if turn.feedback is not None:
        fb = f" verdict={turn.feedback.verdict.value}"
        fb += f" failures={len(turn.feedback.failures)}"
    print(f"  [turn {turn.round}] {turn.guardrail_decision}  "
          f"{turn.action.tool} {_truncate(turn.action.args, 120)}{fb}", flush=True)


def _print_audit(result) -> None:
    print(f"\n=== RUN RESULT ===")
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
    print(f"(key never printed; args truncated to 200 chars)")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run_live")
    p.add_argument("--provider", choices=["deepseek", "anthropic"], default=None,
                   help="override config.yaml llm_provider")
    p.add_argument("--workdir", default=str(Path(__file__).resolve().parent / "target_repo"),
                   help="repo the agent repairs (default: demo/target_repo)")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--from-env", action="store_true",
                   help="read key from env instead of keyring")
    p.add_argument("--yes", action="store_true",
                   help="auto-approve every HITL action (unattended; risky)")
    p.add_argument("--max-rounds", type=int, default=None,
                   help="override config.yaml validator.max_rounds")
    args = p.parse_args(argv)

    cfg = Config.load(args.config)
    provider = args.provider or cfg.llm_provider
    key = _get_key(provider, args.from_env)

    if provider == "deepseek":
        client = DeepSeekClient(api_key=key)
    else:
        client = AnthropicClient(api_key=key)

    tools = for_provider(provider)

    approver = (lambda: True) if args.yes else CliApprover()
    # AutoRejectApprover rejects everything → loop can't make progress; only used
    # in mock tests. For a real run we either HITL (default) or --yes.

    if args.max_rounds is not None:
        cfg.validator.max_rounds = args.max_rounds

    loop = AgentLoop(
        llm=client,
        guardrail=Guardrail(cfg.guardrail),
        approver=approver,
        dispatcher=ToolDispatcher(args.workdir),
        validators={"test": PytestValidator(), "lint": RuffValidator(),
                    "type": MypyValidator()},
        feedback_cfg=cfg.validator,
        memory=Memory(str(Path(cfg.memory_path))),
        system_prompt=SYSTEM_PROMPT,
        tools_schema=tools,
        on_turn=_live_printer,
    )

    print(f"run_live: provider={provider} workdir={args.workdir} "
          f"max_rounds={cfg.validator.max_rounds} hitl={'off(--yes)' if args.yes else 'on'}")
    print("run_live: starting loop (this makes REAL LLM calls — costs tokens)…")
    result = loop.run()
    _print_audit(result)
    return 0 if result.outcome == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
