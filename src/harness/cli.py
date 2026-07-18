"""Harness CLI entrypoint.

Credential hygiene (通用要求 §3.1):
- Keys are NEVER printed. Entry uses getpass (hidden). Status reports only
  "configured" / "not configured".
- Supports view (--status), update (--update-key), and clear (--clear-key)
  commands on top of first-run guided entry (--init-key).
- `.env` loader: a minimal hand-rolled parser (no python-dotenv dependency).
  §3.1 threat-model note: a `.env` file is明文 on disk and visible to the
  process environment — strictly weaker than the OS keyring. Prefer --init-key
  for real credentials; `.env` is provided as a convenience source for
  local/dev only. Existing env vars are NOT overridden.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from harness.config import Config
from harness.credentials import CredentialStore, FakeKeyring
from harness.llm.mock import MockLLMClient
from harness.governance.guardrail import Guardrail
from harness.governance.approver import CliApprover, AutoRejectApprover
from harness.tools.dispatcher import ToolDispatcher
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator
from harness.feedback.feedback_loop import FeedbackLoop
from harness.memory.memory import Memory
from harness.loop import AgentLoop


def _load_env(path: str = ".env") -> int:
    """Load KEY=VALUE lines from a .env file into os.environ.

    Skips blank lines and `#` comments. Does NOT override existing env vars.
    Returns the number of variables loaded. No external dependency.
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


def main(argv=None):
    _load_env(".env")

    p = argparse.ArgumentParser(prog="harness")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--workdir", default=".")
    p.add_argument("--headless", action="store_true", help="run mock demo, no LLM")
    p.add_argument("--init-key", action="store_true", help="guide first-time key entry (hidden)")
    p.add_argument("--status", action="store_true", help="print key status (never the plaintext key)")
    p.add_argument("--update-key", action="store_true", help="update the stored key (hidden entry, overwrites)")
    p.add_argument("--clear-key", action="store_true", help="clear the stored key, then print status")
    args = p.parse_args(argv)

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

    cfg = Config.load(args.config)
    if args.headless:
        # 仅供冒烟, 真实演示走 demo/run_demo.py
        print("headless mode: use `python demo/run_demo.py` for the demo")
        return 0

    # 真实运行: 需 key + provider client (Task 略, 落在 deepseek.py/anthropic_client.py)
    print("not implemented in headless; see demo/run_demo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
