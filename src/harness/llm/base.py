from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class LLMResponse:
    tool: str | None
    args: dict[str, Any] | None
    text: str | None
    parse_error: bool = False
    # tool_call_id: the provider-assigned id for the tool_call. Required to build
    # a compliant OpenAI-style tool-use conversation (the `tool` result message
    # must reference the assistant's tool_call by id). Without it the loop can't
    # echo the assistant tool_call / pair the result → the model can't sustain a
    # multi-turn tool conversation and loops (300x read_file on a real run).
    tool_call_id: str | None = None

class LLMClient(Protocol):
    def complete(self, messages: list, tools_schema: list) -> LLMResponse: ...