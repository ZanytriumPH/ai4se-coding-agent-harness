# src/harness/loop.py
from __future__ import annotations
import json
from harness.models import Action, Feedback, TurnRecord, RunResult, failure_fingerprint
from harness.governance.guardrail import Guardrail, Decision
from harness.feedback.feedback_loop import FeedbackLoop, StopReason
from harness.config import ValidatorConfig
from harness.memory.memory import Memory, RecallQuery

class AgentLoop:
    def __init__(self, llm, guardrail: Guardrail, approver, dispatcher,
                 validators: dict, feedback_cfg: ValidatorConfig, memory: Memory,
                 system_prompt: str = "You repair a failing Python repo.",
                 tools_schema: list | None = None,
                 on_turn=None,
                 max_turns: int | None = None):
        self.llm = llm
        self.guardrail = guardrail
        self.approver = approver
        self.dispatcher = dispatcher
        self.validators = validators
        self.feedback_cfg = feedback_cfg
        self.memory = memory
        self.system_prompt = system_prompt
        # tools_schema: provider-formatted tool defs (see harness.tools.schema).
        # Empty for the mock demo (MockLLMClient ignores it); non-empty for a real
        # LLM so it knows which tools exist. Passed straight through to complete().
        self.tools_schema = tools_schema or []
        # on_turn: optional callback fired after each TurnRecord is finalized.
        # Lets a real-run entry show live per-turn progress instead of going
        # silent for the whole run() (which reads as "hung" to the operator).
        self.on_turn = on_turn
        # Hard turn cap — bounds TOTAL LLM calls, independent of the feedback
        # loop's round counter. The feedback loop only increments on validator
        # turns (run_tests/lint/typecheck); a real LLM can loop forever on
        # read_file/exec_shell (non-validator actions take the `continue` branch
        # and never reach loop.update()). Without this cap such a loop is
        # unbounded → real-run burns tokens indefinitely (mock never triggers).
        # Defaults to feedback_cfg.max_rounds so mock behavior is unchanged.
        self.max_turns = max_turns if max_turns is not None else feedback_cfg.max_rounds
        self.messages: list = []
        self.turns: list[TurnRecord] = []

    def _record(self, turn: TurnRecord) -> None:
        """Append a turn and notify the live observer, if any."""
        self.turns.append(turn)
        if self.on_turn is not None:
            self.on_turn(turn)


    def run(self) -> RunResult:
        self.messages.append({"role": "system", "content": self.system_prompt})
        # 首轮载入项目约定
        conv = self.memory.recall(RecallQuery(tags={"convention"}))
        if conv:
            self.messages.append({"role": "system",
                "content": "PROJECT CONVENTIONS:\n" + "\n".join(e.content for e in conv)})
        loop = FeedbackLoop(validators=self.validators, cfg=self.feedback_cfg)
        stop = StopReason.CONTINUE
        llm_calls = 0
        while stop == StopReason.CONTINUE:
            # Hard turn cap: bound total LLM calls regardless of tool kind.
            # (FeedbackLoop.round only counts validator turns; non-validator
            # actions never reach loop.update(), so without this a stuck LLM
            # looping on read_file/exec_shell runs unbounded.)
            llm_calls += 1
            if llm_calls > self.max_turns:
                stop = StopReason.MAX_ROUNDS
                break
            resp = self.llm.complete(self.messages, tools_schema=self.tools_schema)
            if resp.parse_error or resp.tool is None:
                break
            action = Action(tool=resp.tool, args=resp.args or {})
            # Echo the assistant's tool_call into the conversation so the thread is
            # a compliant OpenAI-style tool-use dialog (assistant tool_call → tool
            # result). Without this the result was fed back as a plain `user`
            # message with no paired tool_call, so the model couldn't tell a tool
            # had actually run and re-issued the same call (300x read_file on a
            # real run). The `tool` result message references the call by id.
            self.messages.append({
                "role": "assistant",
                "content": resp.text or "",
                "tool_calls": [{
                    "id": resp.tool_call_id, "type": "function",
                    "function": {"name": resp.tool,
                                 "arguments": json.dumps(resp.args or {})},
                }],
            })
            decision = self.guardrail.inspect(action)
            guardrail_decision = decision.value

            def _tool_result(content: str) -> None:
                self.messages.append({"role": "tool",
                                      "tool_call_id": resp.tool_call_id,
                                      "content": content})

            if decision == Decision.DENY:
                _tool_result(f"DENIED action: {action.tool} {action.args}")
                self._record(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                stop = StopReason.CONTINUE
                continue
            if decision == Decision.NEED_APPROVAL:
                if not self.approver.approve(action):
                    _tool_result(f"REJECTED by HITL: {action.tool} {action.args}")
                    self._record(TurnRecord(len(self.turns)+1, action, None, "rejected", None))
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
                _tool_result(product.stdout or product.stderr or f"ran {action.tool}")
                self._record(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                continue
            stop, summary = loop.update(feedbacks)
            fp = failure_fingerprint(next(iter(feedbacks.values()))) if feedbacks else None
            _tool_result(summary)
            self._record(TurnRecord(len(self.turns)+1, action, next(iter(feedbacks.values()), None), guardrail_decision, fp))
        outcome_map = {StopReason.SUCCESS: "success", StopReason.NO_PROGRESS: "no_progress", StopReason.MAX_ROUNDS: "max_rounds", StopReason.CONTINUE: "incomplete"}
        return RunResult(outcome=outcome_map[stop], rounds=loop.round, turn_records=self.turns)
