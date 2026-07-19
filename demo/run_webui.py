# demo/run_webui.py
"""Thin wrapper: browser HITL run (serves the webui + drives an AgentLoop).

The real-run logic lives in `harness.cli` (the canonical entrypoint) so this
and the terminal launcher can't drift. This wrapper injects --run-webui and
defaults --workdir to demo/target_repo, then delegates.

Usage (from worktree root, after `pip install -e ".[llm,dev]"` + `harness --init-key`):
    python -m demo.run_webui           # browser HITL, real DeepSeek
    python -m demo.run_webui --mock     # token-free scripted demo (1 approval)
    python -m demo.run_webui --port 8080 --host 0.0.0.0

Equivalent canonical form:
    harness --run-webui --workdir demo/target_repo
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
    if "--run-webui" not in argv:
        argv = ["--run-webui"] + argv
    return cli_main(argv)


if __name__ == "__main__":
    sys.exit(main())
