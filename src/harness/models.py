# src/harness/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class Source(Enum):
    TEST = "test"; LINT = "lint"; TYPE = "type"

class Verdict(Enum):
    PASS = "pass"; FAIL = "fail"

class FailureKind(Enum):
    ASSERTION_ERROR = "assertion_error"
    COLLECTION_ERROR = "collection_error"
    IMPORT_ERROR = "import_error"
    TIMEOUT = "timeout"
    LINT_VIOLATION = "lint_violation"
    TYPE_VIOLATION = "type_violation"
    UNKNOWN = "unknown"

@dataclass
class Action:
    tool: str
    args: dict[str, Any]

@dataclass
class Failure:
    kind: FailureKind
    location: str
    message: str

@dataclass
class Feedback:
    source: Source
    verdict: Verdict
    failures: list[Failure] = field(default_factory=list)

@dataclass
class TurnRecord:
    round: int
    action: Action
    feedback: Feedback | None
    guardrail_decision: str
    failure_fingerprint: frozenset | None

@dataclass
class MemoryEntry:
    id: str
    tags: list[str]
    content: str
    created_at: str

@dataclass
class RunResult:
    outcome: str  # "success" | "no_progress" | "max_rounds"
    rounds: int
    turn_records: list[TurnRecord]

def failure_fingerprint(feedback: Feedback) -> frozenset:
    return frozenset(
        (feedback.source, f.kind, f.location) for f in feedback.failures
    )