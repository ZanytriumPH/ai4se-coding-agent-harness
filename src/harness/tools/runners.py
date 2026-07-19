# src/harness/tools/runners.py
from __future__ import annotations
import os, sys, subprocess, tempfile, json
from .base import Tool, Product

# UTF-8 + errors=replace: on a non-UTF-8 locale (e.g. Chinese-locale Windows =
# GBK/cp936), ``text=True`` alone decodes child stdout with the locale codec.
# pytest's JSON failure report embeds target-repo source lines whose comments
# may be non-ASCII (demo/target_repo has Chinese), producing bytes that aren't
# valid GBK → UnicodeDecodeError in the reader thread crashes the whole tool.
# Pin utf-8/replace so the locale codec is never used.
_ENC = {"encoding": "utf-8", "errors": "replace", "text": True}

class RunTestsTool(Tool):
    name = "run_tests"
    def exec(self, args, workdir):
        # Write the JSON report to a real temp file, not stdout. Real-run exposed
        # that ``--json-report-file=-`` is NOT treated as "stdout" by the installed
        # pytest-json-report version — it writes to a literal file named '-',
        # leaving Product.stdout as pytest's terminal text (F.FFF. / failure dumps),
        # which then crashes PytestValidator.parse with JSONDecodeError. A temp
        # file is version-independent and keeps Product.stdout = pure JSON.
        fd, report_path = tempfile.mkstemp(suffix=".json", prefix="harness_report_")
        os.close(fd)
        try:
            # Invoke as ``python -m pytest`` (sys.executable -m), NOT the ``pytest``
            # console script. The console script does NOT put the workdir on
            # sys.path, so ``from src.app import ...`` in the target repo's tests
            # fails at COLLECTION with ImportError (the real run reported a flat
            # "3 failures" that were actually 3 collection ImportErrors — app.py
            # was never even imported, so the LLM's source edits had no effect and
            # it spent turns debugging sys.path). ``python -m pytest`` adds cwd
            # (workdir) to sys.path[0], the pytest-documented way to run pytest.
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "--json-report",
                 f"--json-report-file={report_path}", "-q"],
                cwd=workdir, capture_output=True, timeout=300, **_ENC)
            stdout = ""
            try:
                with open(report_path, encoding="utf-8", errors="replace") as f:
                    stdout = f.read()
            except OSError:
                stdout = ""  # pytest crashed before writing → empty report
            return Product(r.returncode, stdout, r.stderr)
        finally:
            try:
                os.unlink(report_path)
            except OSError:
                pass

class RunLintTool(Tool):
    name = "run_lint"
    def exec(self, args, workdir):
        r = subprocess.run(["ruff", "check", "--output-format=json", "."],
                           cwd=workdir, capture_output=True, timeout=120,
                           **_ENC)
        return Product(r.returncode, r.stdout, r.stderr)

class RunTypecheckTool(Tool):
    name = "run_typecheck"
    def exec(self, args, workdir):
        r = subprocess.run(["mypy", "--output=json", "src"],
                           cwd=workdir, capture_output=True, timeout=180,
                           **_ENC)
        return Product(r.returncode, r.stdout, r.stderr)