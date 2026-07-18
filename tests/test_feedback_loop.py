# tests/test_feedback_loop.py
from harness.feedback.feedback_loop import FeedbackLoop, StopReason
from harness.models import Source, Verdict, Failure, FailureKind, Feedback
from harness.config import ValidatorConfig
import json


def fb_test_fail():
    return Feedback(source=Source.TEST, verdict=Verdict.FAIL, failures=[
        Failure(FailureKind.ASSERTION_ERROR, "tests/test_a.py::test_x", "m1")])

def fb_pass():
    return Feedback(source=Source.TEST, verdict=Verdict.PASS, failures=[])


def test_success_when_all_pass():
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=10, no_progress_window=3))
    stop, _ = loop.update({"test": fb_pass()})
    assert stop == StopReason.SUCCESS


def test_no_progress_after_window():
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=10, no_progress_window=3))
    for _ in range(2):
        stop, _ = loop.update({"test": fb_test_fail()})
        assert stop == StopReason.CONTINUE
    stop, _ = loop.update({"test": fb_test_fail()})
    assert stop == StopReason.NO_PROGRESS


def test_max_rounds():
    # 构造每次指纹都不同, 避免触发 no_progress
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=2, no_progress_window=99))
    f1 = Feedback(Source.TEST, Verdict.FAIL, [Failure(FailureKind.ASSERTION_ERROR, "loc1", "m")])
    f2 = Feedback(Source.TEST, Verdict.FAIL, [Failure(FailureKind.ASSERTION_ERROR, "loc2", "m")])
    stop, _ = loop.update({"test": f1}); assert stop == StopReason.CONTINUE
    stop, _ = loop.update({"test": f2}); assert stop == StopReason.MAX_ROUNDS


def test_summary_is_structured_not_raw():
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=10, no_progress_window=3))
    _, summary = loop.update({"test": fb_test_fail()})
    assert "FEEDBACK" in summary and "assertion_error" in summary and "tests/test_a.py::test_x" in summary