# src/harness/loop.py
from __future__ import annotations
from harness.models import Action, Feedback, TurnRecord, RunResult, failure_fingerprint
from harness.governance.guardrail import Guardrail, Decision
from harness.feedback.feedback_loop import FeedbackLoop, StopReason
from harness.config import ValidatorConfig
from harness.memory.memory import Memory, RecallQuery

class AgentLoop:
    def __init__(self, llm, guardrail: Guardrail, approver, dispatcher,
                 validators: dict, feedback_cfg: ValidatorConfig, memory: Memory,
                 system_prompt: str = "You repair a failing Python repo."):
        self.llm = llm
        self.guardrail = guardrail
        self.approver = approver
        self.dispatcher = dispatcher
        self.validators = validators
        self.feedback_cfg = feedback_cfg
        self.memory = memory
        self.system_prompt = system_prompt
        self.messages: list = []
        self.turns: list[TurnRecord] = []

    def run(self) -> RunResult:
        self.messages.append({"role": "system", "content": self.system_prompt})
        # 首轮载入项目约定
        conv = self.memory.recall(RecallQuery(tags={"convention"}))
        if conv:
            self.messages.append({"role": "system",
                "content": "PROJECT CONVENTIONS:\n" + "\n".join(e.content for e in conv)})
        loop = FeedbackLoop(validators=self.validators, cfg=self.feedback_cfg)
        stop = StopReason.CONTINUE
        last_feedback: Feedback | None = None
        while stop == StopReason.CONTINUE:
            if last_feedback is not None:
                self.messages.append({"role": "user", "content": last_feedback})
            resp = self.llm.complete(self.messages, tools_schema=[])
            if resp.parse_error or resp.tool is None:
                break
            action = Action(tool=resp.tool, args=resp.args or {})
            decision = self.guardrail.inspect(action)
            guardrail_decision = decision.value
            if decision == Decision.DENY:
                last_feedback = f"DENIED action: {action.tool} {action.args}"
                self.turns.append(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                stop = StopReason.CONTINUE
                continue
            if decision == Decision.NEED_APPROVAL:
                if not self.approver.approve(action):
                    last_feedback = f"REJECTED by HITL: {action.tool} {action.args}"
                    self.turns.append(TurnRecord(len(self.turns)+1, action, None, "rejected", None))
                    continue
            product = self.dispatcher.exec(action)
            feedbacks: dict[str, Feedback] = {}
            if action.tool == "run_tests" and "test" in self.validators:
                feedbacks["test"] = self.validators["test"].parse(product)
            elif action.tool == "run_lint" and "lint" in self.validators:
                feedbacks["lint"] = self.validators["lint"].parse(product)
            elif action.tool == "run_typecheck" and "type" in self.validators:
                feedbacks["type"] = self.validators["type"].parse(product)
            else:
                # 非校验类工具动作, 视为推进, 不更新 stop
                last_feedback = product.stdout or product.stderr or f"ran {action.tool}"
                self.turns.append(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                continue
            stop, summary = loop.update(feedbacks)
            last_feedback = summary
            fp = failure_fingerprint(next(iter(feedbacks.values()))) if feedbacks else None
            self.turns.append(TurnRecord(len(self.turns)+1, action, next(iter(feedbacks.values()), None), guardrail_decision, fp))
        outcome_map = {StopReason.SUCCESS: "success", StopReason.NO_PROGRESS: "no_progress", StopReason.MAX_ROUNDS: "max_rounds", StopReason.CONTINUE: "incomplete"}
        return RunResult(outcome=outcome_map[stop], rounds=loop.round, turn_records=self.turns)
