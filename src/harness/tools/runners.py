# src/harness/tools/runners.py
from __future__ import annotations
import subprocess, json
from .base import Tool, Product

class RunTestsTool(Tool):
    name = "run_tests"
    def exec(self, args, workdir):
        r = subprocess.run(["pytest", "--json-report", "--json-report-file=-"],
                           cwd=workdir, capture_output=True, text=True, timeout=300)
        return Product(r.returncode, r.stdout, r.stderr)

class RunLintTool(Tool):
    name = "run_lint"
    def exec(self, args, workdir):
        r = subprocess.run(["ruff", "check", "--output-format=json", "."],
                           cwd=workdir, capture_output=True, text=True, timeout=120)
        return Product(r.returncode, r.stdout, r.stderr)

class RunTypecheckTool(Tool):
    name = "run_typecheck"
    def exec(self, args, workdir):
        r = subprocess.run(["mypy", "--output=json", "src"],
                           cwd=workdir, capture_output=True, text=True, timeout=180)
        return Product(r.returncode, r.stdout, r.stderr)