# tests/test_runners_encoding.py
"""Pin the subprocess encoding fix.

On a Chinese-locale Windows, ``subprocess.run(text=True)`` defaults to the GBK
codec. pytest's JSON failure report embeds source lines from the target repo,
and demo/target_repo/src/app.py has Chinese comments — those UTF-8 bytes are
not valid GBK, so the reader thread raises UnicodeDecodeError and crashes the
whole RunTestsTool (real-run surfaced this; mock never triggers it).

The fix: every runner passes ``encoding="utf-8", errors="replace"`` so the
locale codec is never used. These tests pin that contract by capturing the
kwargs handed to subprocess.run.
"""
import subprocess
import sys

from harness.tools.runners import RunTestsTool, RunLintTool, RunTypecheckTool
from harness.models import Action
import json as _json


def _capturing_run(cap):
    def _f(cmd, **kwargs):
        cap.update(kwargs)
        cap["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout="[]", stderr="")
    return _f


def _cap(monkeypatch):
    cap: dict = {}
    monkeypatch.setattr("harness.tools.runners.subprocess.run", _capturing_run(cap))
    return cap


def test_run_tests_uses_utf8_with_replace(monkeypatch):
    cap = _cap(monkeypatch)
    RunTestsTool().exec(Action("run_tests", {}), workdir=".")
    assert cap["encoding"] == "utf-8"
    assert cap["errors"] == "replace"


def test_run_lint_uses_utf8_with_replace(monkeypatch):
    cap = _cap(monkeypatch)
    RunLintTool().exec(Action("run_lint", {}), workdir=".")
    assert cap["encoding"] == "utf-8"
    assert cap["errors"] == "replace"


def test_run_typecheck_uses_utf8_with_replace(monkeypatch):
    cap = _cap(monkeypatch)
    RunTypecheckTool().exec(Action("run_typecheck", {}), workdir=".")
    assert cap["encoding"] == "utf-8"
    assert cap["errors"] == "replace"


def test_run_tests_reads_json_from_report_file(monkeypatch, tmp_path):
    # --json-report-file=- writes to a literal file '-' on the installed plugin
    # version, NOT stdout — so stdout would be pytest's terminal text and
    # PytestValidator would crash on json.loads. RunTestsTool must write the
    # report to a real temp file and return its contents as Product.stdout.
    seen_cmd = {}

    def fake_run(cmd, **kwargs):
        path = next(a.split("=", 1)[1] for a in cmd
                    if a.startswith("--json-report-file="))
        with open(path, "w", encoding="utf-8") as f:
            f.write(_json.dumps({"tests": [], "collectors": []}))
        seen_cmd["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("harness.tools.runners.subprocess.run", fake_run)
    p = RunTestsTool().exec(Action("run_tests", {}), workdir=str(tmp_path))
    # Product.stdout must be the JSON report, not pytest's terminal text
    assert _json.loads(p.stdout) == {"tests": [], "collectors": []}
    assert any(a.startswith("--json-report-file=") and a != "--json-report-file=-"
               for a in seen_cmd["cmd"]), "must not use the literal '-' target"


def test_run_tests_invokes_python_minus_m_pytest(monkeypatch, tmp_path):
    # The ``pytest`` console script does NOT put the workdir on sys.path, so
    # ``from src.app import ...`` fails at COLLECTION with ImportError (the real
    # run's flat "3 failures" were actually 3 collection ImportErrors — app.py
    # was never imported). Must invoke as ``<python> -m pytest`` so cwd lands on
    # sys.path[0], the pytest-documented invocation.
    cap = _cap(monkeypatch)
    RunTestsTool().exec(Action("run_tests", {}), workdir=str(tmp_path))
    cmd = cap["cmd"]
    assert cmd[0] == sys.executable
    assert cmd[1] == "-m"
    assert cmd[2] == "pytest"
