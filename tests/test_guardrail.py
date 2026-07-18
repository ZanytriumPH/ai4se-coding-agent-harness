# tests/test_guardrail.py
from harness.config import GuardrailRules
from harness.governance.guardrail import Guardrail, Decision
from harness.models import Action


def rules():
    return GuardrailRules(
        deny_paths=[".env", ".gitlab-ci.yml"],
        deny_path_globs=[".github/**"],
        network_whitelist=["pip install", "npm install"],
        network_blacklist=["curl", "wget"],
        git_block=["push"],
        shell_blacklist=["rm -rf", "sudo", "DROP", "TRUNCATE"],
    )


def test_write_to_env_is_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": ".env", "content": "x"})) == Decision.DENY


def test_path_escape_needs_approval():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": "../../etc/passwd", "content": "x"})) == Decision.NEED_APPROVAL


def test_destructive_shell_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "rm -rf /"})) == Decision.DENY


def test_git_push_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "git push origin main"})) == Decision.DENY


def test_pip_install_allowed():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "pip install ruff"})) == Decision.ALLOW


def test_curl_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "curl http://x"})) == Decision.DENY


def test_normal_write_allowed():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": "src/app.py", "content": "x"})) == Decision.ALLOW


def test_absolute_path_needs_approval():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": "/etc/passwd", "content": "x"})) == Decision.NEED_APPROVAL