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

def test_pytest_validator_classifies_module_not_found_as_import_error():
    v = PytestValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("pytest_fail.json")), stderr=""))
    kinds = {(f.kind, f.location) for f in fb.failures}
    assert (FailureKind.IMPORT_ERROR, "tests/test_db.py::test_conn") in kinds

def test_pytest_validator_collection_error_not_false_pass():
    # collection-phase crash (e.g. ImportError in conftest) → empty "tests",
    # failed "collectors". Must NOT be misreported as PASS.
    v = PytestValidator()
    fb = v.parse(Product(exitcode=2, stdout=json.dumps(load("pytest_collection_error.json")), stderr=""))
    assert fb.verdict == Verdict.FAIL
    assert any(f.kind == FailureKind.COLLECTION_ERROR for f in fb.failures)

def test_ruff_validator_survives_malformed_item():
    # ruff entry missing 'location'/'code' — must not KeyError-crash the loop.
    v = RuffValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps([{"filename": "a.py"}]), stderr=""))
    assert fb.source == Source.LINT  # did not raise
    assert fb.verdict == Verdict.PASS  # malformed entry skipped, no classified failure

def test_mypy_validator_survives_malformed_item():
    # mypy error entry missing 'line' — must not KeyError-crash the loop.
    v = MypyValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps([{"file": "a.py", "type": "error"}]), stderr=""))
    assert fb.source == Source.TYPE  # did not raise
    assert fb.verdict == Verdict.PASS