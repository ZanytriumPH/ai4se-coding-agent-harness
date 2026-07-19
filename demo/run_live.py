# demo/run_live.py
"""Thin wrapper: terminal HITL run against a real LLM.

The real-run logic lives in `harness.cli` (the canonical entrypoint) so this
and the webui launcher can't drift. This wrapper just defaults --workdir to
demo/target_repo and delegates.

Usage (from worktree root, after `pip install -e ".[llm,dev]"` + `harness --init-key`):
    python -m demo.run_live                # DeepSeek, HITL on, workdir=demo/target_repo
    python -m demo.run_live --provider anthropic
    python -m demo.run_live --yes          # auto-approve all HITL (unattended)

Equivalent canonical form:
    harness --workdir demo/target_repo
"""
from __future__ import annotations

import sys
from pathlib import Path

from harness.cli import main as cli_main

_DEFAULT_WORKDIR = str(Path(__file__).resolve().parent / "target_repo")


def main(argv=None) -> int:
    argv = list(argv) if argv else sys.argv[1:]
    if not any(a == "--workdir" or a.startswith("--workdir=") for a in argv):
        argv = ["--workdir", _DEFAULT_WORKDIR] + argv
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
