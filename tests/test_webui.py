from harness.governance.approver import WebApprover
from harness.models import Action


def test_web_approver_uses_injected_ask():
    called = {}
    def ask(a):
        called["action"] = a
        return True
    ap = WebApprover(ask=ask)
    assert ap.approve(Action("write_file", {"path": "../x", "content": "y"})) is True
    assert called["action"].tool == "write_file"
