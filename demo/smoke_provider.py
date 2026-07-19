# demo/smoke_provider.py
"""Provider smoke test (step 1 of real end-to-end).

Purpose: isolate "does the real LLM provider work?" from "does the loop work?".
Verifies, in one shot: network reachability, auth (key validity), and the
client's tool_call parsing path — against a REAL API endpoint, not MockTransport.

Credential hygiene (通用要求 §3.1):
- Reads the key from the OS keyring via CredentialStore (same path the CLI uses).
- The key is NEVER printed / logged. Only the parsed LLMResponse fields are shown.
- An env-var fallback (DEEPSEEK_API_KEY / ANTHROPIC_API_KEY) is provided for CI
  convenience, but §3.1 notes env is明文 and strictly weaker than the keyring —
  prefer `harness --init-key` for real keys.

Usage:
    python -m demo.smoke_provider                     # DeepSeek, key from keyring
    python -m demo.smoke_provider --provider anthropic
    DEEPSEEK_API_KEY=sk-... python -m demo.smoke_provider --from-env

Exit code 0 = smoke passed (auth ok + tool_call parsed). Nonzero = failed,
with the HTTP status / error surfaced so you can tell 401 from timeout.
"""
from __future__ import annotations

import argparse
import os
import sys

from harness.credentials import CredentialStore
from harness.llm.deepseek import DeepSeekClient
from harness.llm.anthropic_client import AnthropicClient
from harness.llm.base import LLMResponse


def _get_key(provider: str, from_env: bool) -> str:
    if from_env:
        env_var = "DEEPSEEK_API_KEY" if provider == "deepseek" else "ANTHROPIC_API_KEY"
        key = os.environ.get(env_var)
        if not key:
            sys.exit(f"smoke: --from-env set but {env_var} is empty")
        return key
    key = CredentialStore().get()
    if not key:
        sys.exit("smoke: no key in keyring — run `harness --init-key` first")
    return key


# Minimal tool schema per provider — just enough to exercise the tool_call
# round-trip. Real 6-tool schema is step 2 (wiring the loop). This is a smoke,
# not a loop run.
_DEEPSEEK_TOOL = [{
    "type": "function",
    "function": {
        "name": "reply",
        "description": "Reply with a single word.",
        "parameters": {
            "type": "object",
            "properties": {"word": {"type": "string"}},
            "required": ["word"],
        },
    },
}]
_ANTHROPIC_TOOL = [{
    "name": "reply",
    "description": "Reply with a single word.",
    "input_schema": {
        "type": "object",
        "properties": {"word": {"type": "string"}},
        "required": ["word"],
    },
}]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="smoke_provider")
    p.add_argument("--provider", choices=["deepseek", "anthropic"], default="deepseek")
    p.add_argument("--from-env", action="store_true",
                   help="read key from DEEPSEEK_API_KEY/ANTHROPIC_API_KEY instead of keyring")
    args = p.parse_args(argv)

    key = _get_key(args.provider, args.from_env)

    if args.provider == "deepseek":
        client = DeepSeekClient(api_key=key)
        tools = _DEEPSEEK_TOOL
        msg = "Call the reply tool with word='ok'. Reply with nothing else."
    else:
        client = AnthropicClient(api_key=key)
        tools = _ANTHROPIC_TOOL
        msg = "Use the reply tool with word='ok'."

    messages = [{"role": "user", "content": msg}]

    # httpx raises on network error; resp.raise_for_status() surfaces 4xx/5xx.
    try:
        resp: LLMResponse = client.complete(messages, tools_schema=tools)
    except Exception as e:
        print(f"smoke: request FAILED — {type(e).__name__}: {e}")
        return 2

    print("smoke: request OK (auth + network)")
    print(f"  parse_error = {resp.parse_error}")
    print(f"  tool        = {resp.tool}")
    print(f"  args        = {resp.args}")
    if resp.text:
        print(f"  text        = {resp.text[:120]}")

    if resp.parse_error:
        print("smoke: FAIL — parse_error (tool_call present but unparseable)")
        return 3
    if resp.tool != "reply" or not (resp.args or {}).get("word"):
        print("smoke: FAIL — LLM did not return the expected tool_call")
        return 4
    print("smoke: PASS — auth ok, tool_call parsed correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
