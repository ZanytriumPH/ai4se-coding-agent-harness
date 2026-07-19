# src/harness/feedback/feedback_loop.py
from __future__ import annotations
from enum import Enum
from harness.models import Feedback, Verdict, failure_fingerprint
from harness.config import ValidatorConfig


class StopReason(Enum):
    CONTINUE = "continue"
    SUCCESS = "success"
    NO_PROGRESS = "no_progress"
    MAX_ROUNDS = "max_rounds"


class FeedbackLoop:
    def __init__(self, validators: dict, cfg: ValidatorConfig):
        self.validators = validators
        self.cfg = cfg
        self.round = 0
        self.history: list[frozenset] = []

    def update(self, feedbacks: dict[str, Feedback]) -> tuple[StopReason, str]:
        self.round += 1
        all_pass = all(f.verdict == Verdict.PASS for f in feedbacks.values()) if feedbacks else True
        summary = self._summarize(feedbacks)
        if all_pass:
            return StopReason.SUCCESS, summary
        fp = frozenset().union(*(failure_fingerprint(f) for f in feedbacks.values()))
        self.history.append(fp)
        if self.round >= self.cfg.max_rounds:
            return StopReason.MAX_ROUNDS, summary
        if self._no_progress(fp):
            return StopReason.NO_PROGRESS, summary
        return StopReason.CONTINUE, summary

    def _no_progress(self, current: frozenset) -> bool:
        if len(self.history) < self.cfg.no_progress_window:
            return False
        window = self.history[-(self.cfg.no_progress_window):]
        return all(w == current for w in window)

    def _summarize(self, feedbacks: dict[str, Feedback]) -> str:
        lines = ["FEEDBACK"]
        for name, f in feedbacks.items():
            lines.append(f"[{name} source={f.source.value} verdict={f.verdict.value}]")
            for fl in f.failures:
                lines.append(f"- [{fl.kind.value}] {fl.location} : {fl.message}")
        lines.append(f"PROGRESS: round {self.round}/{self.cfg.max_rounds}")
        return "\n".join(lines)