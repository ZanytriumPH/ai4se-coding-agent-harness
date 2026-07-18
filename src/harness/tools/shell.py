# src/harness/tools/shell.py
from __future__ import annotations
import subprocess
from .base import Tool, Product

class ExecShellTool(Tool):
    name = "exec_shell"
    def exec(self, args, workdir):
        r = subprocess.run(args["cmd"], shell=True, cwd=workdir,
                            capture_output=True, text=True, timeout=120)
        return Product(r.returncode, r.stdout, r.stderr)