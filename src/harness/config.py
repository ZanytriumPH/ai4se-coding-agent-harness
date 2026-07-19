# src/harness/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

# Single source of truth for the path-escape guardrail default. Hardened
# (PR-6 #7): POSIX abs (^/) + traversal (..) + Windows drive (C:\) + UNC (\\).
# Referenced by BOTH the GuardrailRules dataclass field AND Config.load()'s
# fallback — a custom config.yaml omitting escape_regex must NOT silently
# regress to a weaker POSIX-only literal (that would let C:\ / \\ bypass the
# guardrail). Keeping one constant guarantees the two can't drift.
_DEFAULT_ESCAPE_REGEX = r"(^/)|(\.\.)|(^([A-Za-z]:[\\/]))|(^\\\\)"

@dataclass
class GuardrailRules:
    deny_paths: list[str] = field(default_factory=list)
    deny_path_globs: list[str] = field(default_factory=list)
    network_whitelist: list[str] = field(default_factory=list)
    network_blacklist: list[str] = field(default_factory=list)
    git_block: list[str] = field(default_factory=list)
    shell_blacklist: list[str] = field(default_factory=list)
    escape_regex: str = _DEFAULT_ESCAPE_REGEX  # 绝对路径(POSIX ^/ 或 Windows C:\ 或 UNC \\) 或 目录穿越(..) → NeedApproval; 不匹配普通子路径 src/app.py

@dataclass
class ValidatorConfig:
    max_rounds: int = 10
    no_progress_window: int = 3

@dataclass
class Config:
    llm_provider: str = "deepseek"
    memory_path: str = ".agent_memory/"
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)
    guardrail: GuardrailRules = field(default_factory=GuardrailRules)

    @classmethod
    def load(cls, path: str) -> "Config":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        g = data.get("guardrail", {})
        v = data.get("validator", {})
        return cls(
            llm_provider=data.get("llm_provider", "deepseek"),
            memory_path=data.get("memory_path", ".agent_memory/"),
            validator=ValidatorConfig(
                max_rounds=v.get("max_rounds", 10),
                no_progress_window=v.get("no_progress_window", 3),
            ),
            guardrail=GuardrailRules(
                deny_paths=g.get("deny_paths", []),
                deny_path_globs=g.get("deny_path_globs", []),
                network_whitelist=g.get("network_whitelist", []),
                network_blacklist=g.get("network_blacklist", []),
                git_block=g.get("git_block", []),
                shell_blacklist=g.get("shell_blacklist", []),
                escape_regex=g.get("escape_regex", _DEFAULT_ESCAPE_REGEX),
            ),
        )