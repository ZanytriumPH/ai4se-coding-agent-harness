from __future__ import annotations
import json
from dataclasses import dataclass
from harness.models import Source, Verdict, FailureKind, Feedback, Failure

@dataclass
class Product:
    exitcode: int
    stdout: str
    stderr: str

class Validator:
    def parse(self, product: Product) -> Feedback: ...

class PytestValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        raw = product.stdout or ""
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            # Non-JSON stdout (e.g. a plugin-version regression that writes the
            # report to a file instead of stdout, or pytest crashing before the
            # report). A crash here would kill the whole loop; degrade to a
            # single UNKNOWN failure with verdict=FAIL so the agent is told tests
            # did not run cleanly, instead of crashing or false-PASSing.
            return Feedback(source=Source.TEST, verdict=Verdict.FAIL,
                            failures=[Failure(kind=FailureKind.UNKNOWN, location="",
                                              message="non-JSON pytest stdout (report missing/unparseable)")])
        failures: list[Failure] = []
        for t in data.get("tests", []):
            if t.get("outcome") in ("failed", "error"):
                crash = t.get("call", {}).get("crash", {})
                ctype = crash.get("type", "")
                kind = (FailureKind.IMPORT_ERROR
                        if ctype in ("ImportError", "ModuleNotFoundError") or "Import" in ctype
                        else FailureKind.ASSERTION_ERROR)
                failures.append(Failure(kind=kind, location=t["nodeid"], message=crash.get("message", "")))
        # Collection-phase crashes: tests collected fine but a collector failed
        # (e.g. ImportError in conftest / module). pytest --json-report puts these
        # in "collectors", not "tests" — without this check an empty "tests" array
        # would yield a false PASS.
        for c in data.get("collectors", []):
            if c.get("outcome") == "failed":
                longrepr = c.get("longrepr", "") or ""
                tail = longrepr.splitlines()[-1] if longrepr else ""
                failures.append(Failure(kind=FailureKind.COLLECTION_ERROR,
                                        location=c.get("nodeid", ""),
                                        message=tail))
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.TEST, verdict=verdict, failures=failures)

class RuffValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        items = json.loads(product.stdout or "[]")
        failures = []
        for it in items:
            loc = it.get("location")
            if not isinstance(loc, dict) or "row" not in loc \
                    or "filename" not in it or "code" not in it:
                continue  # malformed ruff entry — skip, don't KeyError-crash the loop
            failures.append(Failure(kind=FailureKind.LINT_VIOLATION,
                    location=f"{it['filename']}:{loc['row']}",
                    message=f"{it['code']}: {it.get('message', '')}"))
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.LINT, verdict=verdict, failures=failures)

class MypyValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        items = json.loads(product.stdout or "[]")
        failures = []
        for it in items:
            if it.get("type") == "error" and "file" in it and "line" in it:
                failures.append(Failure(kind=FailureKind.TYPE_VIOLATION,
                        location=f"{it['file']}:{it['line']}",
                        message=it.get("message", "")))
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.TYPE, verdict=verdict, failures=failures)