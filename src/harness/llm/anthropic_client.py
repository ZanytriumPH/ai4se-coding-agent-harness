from __future__ import annotations
import httpx
from .base import LLMResponse


class AnthropicClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None,
                 model: str = "claude-sonnet-5"):
        self.api_key = api_key
        self.model = model
        self.http = http_client or httpx.Client()

    def complete(self, messages, tools_schema) -> LLMResponse:
        resp = self.http.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={"model": self.model, "max_tokens": 1024,
                  "messages": messages, "tools": tools_schema or None},
            timeout=60,
        )
        resp.raise_for_status()
        for block in resp.json().get("content", []):
            if block.get("type") == "tool_use":
                return LLMResponse(tool=block.get("name"), args=block.get("input", {}),
                                   text=None, parse_error=False)
            if block.get("type") == "text":
                return LLMResponse(tool=None, args=None, text=block.get("text"),
                                   parse_error=False)
        return LLMResponse(tool=None, args=None, text=None, parse_error=True)