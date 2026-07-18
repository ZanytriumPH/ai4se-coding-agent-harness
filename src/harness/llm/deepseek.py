from __future__ import annotations
import json
import httpx
from .base import LLMResponse


class DeepSeekClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None,
                 model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.http = http_client or httpx.Client()

    def complete(self, messages, tools_schema) -> LLMResponse:
        resp = self.http.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages,
                  "tools": tools_schema or None},
            timeout=60,
        )
        resp.raise_for_status()
        msg = (resp.json().get("choices") or [{}])[0].get("message", {})
        tcs = msg.get("tool_calls") or []
        if not tcs:
            return LLMResponse(tool=None, args=None, text=msg.get("content"), parse_error=False)
        fn = tcs[0].get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            return LLMResponse(tool=None, args=None, text=None, parse_error=True)
        return LLMResponse(tool=fn.get("name"), args=args, text=None, parse_error=False)