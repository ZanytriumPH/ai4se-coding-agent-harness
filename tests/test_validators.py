import json
from pathlib import Path
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator, Product
from harness.models import Source, Verdict, FailureKind

FIX = Path(__file__).parent / "fixtures"

def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))

def test_pytest_validator_classifies_failures():
    v = PytestValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("pytest_fail.json")), stderr=""))
    assert fb.source == Source.TEST and fb.verdict == Verdict.FAIL
    kinds = {(f.kind, f.location) for f in fb.failures}
    assert (FailureKind.ASSERTION_ERROR, "tests/test_a.py::test_login") in kinds
    assert (FailureKind.IMPORT_ERROR, "tests/test_db.py::test_conn") in kinds

def test_pytest_validator_pass():
    v = PytestValidator()
    fb = v.parse(Product(exitcode=0, stdout=json.dumps(load("pytest_pass.json")), stderr=""))
    assert fb.verdict == Verdict.PASS and fb.failures == []

def test_ruff_validator_classifies_lint():
    v = RuffValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("ruff_fail.json")), stderr=""))
    assert fb.source == Source.LINT and fb.verdict == Verdict.FAIL
    f = fb.failures[0]
    assert f.kind == FailureKind.LINT_VIOLATION and f.location == "src/app.py:12"

def test_mypy_validator_classifies_type():
    v = MypyValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("mypy_fail.json")), stderr=""))
    assert fb.source == Source.TYPE and fb.verdict == Verdict.FAIL
    f = fb.failures[0]
    assert f.kind == FailureKind.TYPE_VIOLATION and f.location == "src/app.py:8"