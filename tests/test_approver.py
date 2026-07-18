# tests/test_approver.py
from harness.governance.approver import AutoRejectApprover
from harness.models import Action


def test_auto_reject_returns_false_without_io():
    a = AutoRejectApprover()
    assert a.approve(Action("write_file", {"path": "../../etc", "content": "x"})) is False