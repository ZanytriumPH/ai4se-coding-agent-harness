from harness.governance.approver import WebApprover
from harness.models import Action
from webui.server import WebUISession
import threading


def test_web_approver_uses_injected_ask():
    called = {}
    def ask(a):
        called["action"] = a
        return True
    ap = WebApprover(ask=ask)
    assert ap.approve(Action("write_file", {"path": "../x", "content": "y"})) is True
    assert called["action"].tool == "write_file"


def test_pending_action_peeks_without_consuming():
    # /pending polls every ~1s in the browser. ask() must park the action where
    # /pending can PEEK it repeatedly without consuming — otherwise the 2nd poll
    # hides the approval card while ask() still blocks, leaving the UI showing
    # nothing and the loop stuck. (This is exactly what a real browser run hit.)
    s = WebUISession()
    act = Action("write_file", {"path": "/etc/g.py", "content": "x"})
    result = {}

    def _asker():
        result["decision"] = s.ask(act)

    t = threading.Thread(target=_asker)
    t.start()

    # give ask() a moment to park the action
    import time; time.sleep(0.1)
    # repeated peeks all see the SAME action (not consumed)
    assert s.pending_action() is act
    assert s.pending_action() is act  # still there after 2nd peek

    s.answer(True)
    t.join(timeout=2)
    assert result.get("decision") is True
    assert s.pending_action() is None  # cleared once answered
