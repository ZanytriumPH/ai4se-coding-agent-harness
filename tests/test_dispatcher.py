# tests/test_dispatcher.py
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.base import Product
from harness.models import Action

def test_write_then_read(tmp_path):
    d = ToolDispatcher(workdir=str(tmp_path))
    w = d.exec(Action("write_file", {"path": "a.py", "content": "x=1"}))
    assert w.exitcode == 0
    r = d.exec(Action("read_file", {"path": "a.py"}))
    assert "x=1" in r.stdout

def test_write_escape_rejected(tmp_path):
    d = ToolDispatcher(workdir=str(tmp_path))
    p = d.exec(Action("write_file", {"path": "../escape.py", "content": "x"}))
    assert p.exitcode != 0 and "escape" in (p.stderr + p.stdout).lower()

def test_exec_shell_runs(tmp_path):
    d = ToolDispatcher(workdir=str(tmp_path))
    p = d.exec(Action("exec_shell", {"cmd": "echo hi"}))
    assert "hi" in p.stdout

def test_sibling_prefix_escape_rejected(tmp_path):
    # A sibling dir whose name extends the workdir basename must NOT bypass the guard.
    sibling = tmp_path.parent / (tmp_path.name + "X")
    sibling.mkdir(exist_ok=True)
    d = ToolDispatcher(workdir=str(tmp_path))
    p = d.exec(Action("write_file", {"path": f"../{tmp_path.name}X/evil.py", "content": "x"}))
    assert p.exitcode != 0
    assert "escape" in (p.stderr + p.stdout).lower()