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
        data = json.loads(product.stdout or "{}")
        failures: list[Failure] = []
        for t in data.get("tests", []):
            if t.get("outcome") in ("failed", "error"):
                crash = t.get("call", {}).get("crash", {})
                ctype = crash.get("type", "")
                kind = FailureKind.IMPORT_ERROR if "Import" in ctype else FailureKind.ASSERTION_ERROR
                failures.append(Failure(kind=kind, location=t["nodeid"], message=crash.get("message", "")))
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.TEST, verdict=verdict, failures=failures)

class RuffValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        items = json.loads(product.stdout or "[]")
        failures = [
            Failure(kind=FailureKind.LINT_VIOLATION,
                    location=f"{it['filename']}:{it['location']['row']}",
                    message=f"{it['code']}: {it['message']}")
            for it in items
        ]
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.LINT, verdict=verdict, failures=failures)

class MypyValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        items = json.loads(product.stdout or "[]")
        failures = [
            Failure(kind=FailureKind.TYPE_VIOLATION,
                    location=f"{it['file']}:{it['line']}",
                    message=it.get("message", ""))
            for it in items if it.get("type") == "error"
        ]
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.TYPE, verdict=verdict, failures=failures)