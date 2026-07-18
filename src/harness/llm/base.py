from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class LLMResponse:
    tool: str | None
    args: dict[str, Any] | None
    text: str | None
    parse_error: bool = False

class LLMClient(Protocol):
    def complete(self, messages: list, tools_schema: list) -> LLMResponse: ...