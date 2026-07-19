# src/harness/tools/schema.py
"""Tool JSON-Schema definitions, per-provider formatted.

Why this module exists (盲点 2 / REFLECTION §A.4-C):
The loop previously passed ``tools_schema=[]`` to the LLM, so a *real* LLM
had no way to know which tools exist or how to fill their args — it would
reply as plain text, ``resp.tool is None``, and the loop would break with
``outcome="incomplete"``. That looked like "LLM can't do it" but was really a
wiring gap. This module is the wiring.

Two output shapes are needed because the two provider clients pass the schema
straight through to their respective APIs:
- DeepSeek (OpenAI-style): ``{"type":"function","function":{name,description,parameters}}``
- Anthropic:                ``{name,description,input_schema}``

The canonical arg set is defined once (TOOL_SCHEMAS) and must stay in lock-step
with the tools' ``exec(args, workdir)`` signatures in files.py / shell.py /
runners.py. A drift here = the next bug (see PLAN-self-consistency lesson,
REFLECTION §四).
"""
from __future__ import annotations

# Canonical, provider-agnostic tool descriptors.
# Each entry: name -> (description, JSON-Schema parameters object).
# Args MUST match the tools' exec(args) signatures exactly:
#   read_file / write_file / exec_shell come from files.py / shell.py
#   run_tests / run_lint / run_typecheck come from runners.py (no args)
TOOL_SCHEMAS: dict[str, tuple[str, dict]] = {
    "read_file": (
        "Read a UTF-8 text file under the work directory. Returns file contents.",
        {"type": "object",
         "properties": {"path": {"type": "string",
                                 "description": "Repo-relative path, e.g. 'src/app.py'"}},
         "required": ["path"]},
    ),
    "write_file": (
        "Write (overwrite) a UTF-8 text file under the work directory. "
        "Creates parent dirs. Paths escaping the workdir are blocked by the guardrail.",
        {"type": "object",
         "properties": {
             "path": {"type": "string", "description": "Repo-relative path."},
             "content": {"type": "string", "description": "Full file content to write."},
         },
         "required": ["path", "content"]},
    ),
    "exec_shell": (
        "Run a shell command in the work directory. Destructive/network/git-push "
        "commands are blocked by the guardrail.",
        {"type": "object",
         "properties": {"cmd": {"type": "string", "description": "Shell command string."}},
         "required": ["cmd"]},
    ),
    "run_tests": (
        "Run the repo's test suite (pytest --json-report). Returns a JSON report; "
        "passing tests yield verdict=PASS.",
        {"type": "object", "properties": {}, "required": []},
    ),
    "run_lint": (
        "Run ruff over the repo. Returns JSON violations.",
        {"type": "object", "properties": {}, "required": []},
    ),
    "run_typecheck": (
        "Run mypy over the repo's src. Returns JSON type errors.",
        {"type": "object", "properties": {}, "required": []},
    ),
}


def for_provider(provider: str, names: list[str] | None = None) -> list[dict]:
    """Build the tools schema list in the format the given provider's API expects.

    ``provider``: "deepseek" (OpenAI tool-call shape) or "anthropic".
    ``names``: subset of TOOL_SCHEMAS keys to include; None = all six.
    """
    if provider not in ("deepseek", "anthropic"):
        raise ValueError(f"unknown provider: {provider!r}")
    selected = names or list(TOOL_SCHEMAS.keys())
    unknown = [n for n in selected if n not in TOOL_SCHEMAS]
    if unknown:
        raise ValueError(f"unknown tool name(s): {unknown}")
    if provider == "deepseek":
        return [{"type": "function",
                 "function": {"name": n, "description": desc, "parameters": params}}
                for n, (desc, params) in ((n, TOOL_SCHEMAS[n]) for n in selected)]
    # anthropic
    return [{"name": n, "description": desc, "input_schema": params}
            for n, (desc, params) in ((n, TOOL_SCHEMAS[n]) for n in selected)]
