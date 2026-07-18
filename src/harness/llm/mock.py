from __future__ import annotations
from .base import LLMResponse

class MockLLMClient:
    def __init__(self, script: list[LLMResponse]):
        self._script = list(script)
        self._idx = 0

    def complete(self, messages: list, tools_schema: list) -> LLMResponse:
        if self._idx >= len(self._script):
            return LLMResponse(tool=None, args=None, text=None, parse_error=True)
        r = self._script[self._idx]
        self._idx += 1
        return r