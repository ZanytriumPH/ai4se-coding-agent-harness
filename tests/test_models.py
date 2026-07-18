# tests/test_models.py
from harness.models import (
    Source, Verdict, FailureKind, Action, Failure, Feedback,
    failure_fingerprint,
)

def test_failure_fingerprint_ignores_message():
    f1 = Feedback(source=Source.TEST, verdict=Verdict.FAIL, failures=[
        Failure(kind=FailureKind.ASSERTION_ERROR, location="tests/test_a.py::test_x", message="exp 200 got 401"),
    ])
    f2 = Feedback(source=Source.TEST, verdict=Verdict.FAIL, failures=[
        Failure(kind=FailureKind.ASSERTION_ERROR, location="tests/test_a.py::test_x", message="exp 200 got 500"),
    ])
    assert failure_fingerprint(f1) == failure_fingerprint(f2)
    assert failure_fingerprint(f1) == frozenset({(Source.TEST, FailureKind.ASSERTION_ERROR, "tests/test_a.py::test_x")})

def test_pass_feedback_has_empty_fingerprint():
    f = Feedback(source=Source.TEST, verdict=Verdict.PASS, failures=[])
    assert failure_fingerprint(f) == frozenset()