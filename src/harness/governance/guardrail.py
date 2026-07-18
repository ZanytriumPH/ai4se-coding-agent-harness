# src/harness/governance/guardrail.py
from __future__ import annotations
import re
from enum import Enum
from fnmatch import fnmatch
from harness.config import GuardrailRules
from harness.models import Action


class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEED_APPROVAL = "need_approval"


class Guardrail:
    def __init__(self, rules: GuardrailRules):
        self.rules = rules

    def inspect(self, action: Action) -> Decision:
        if action.tool == "write_file":
            return self._check_write(action)
        if action.tool == "exec_shell":
            return self._check_shell(action)
        return Decision.ALLOW

    def _check_write(self, action: Action) -> Decision:
        path = action.args.get("path", "")
        if any(path == p or path.startswith(p + "/") for p in self.rules.deny_paths):
            return Decision.DENY
        if any(fnmatch(path, g) for g in self.rules.deny_path_globs):
            return Decision.DENY
        if re.search(self.rules.escape_regex, path):
            return Decision.NEED_APPROVAL
        return Decision.ALLOW

    def _check_shell(self, action: Action) -> Decision:
        cmd = action.args.get("cmd", "")
        for bad in self.rules.shell_blacklist:
            if bad in cmd:
                return Decision.DENY
        for bad in self.rules.network_blacklist:
            if re.search(rf"\b{re.escape(bad)}\b", cmd):
                return Decision.DENY
        if cmd.strip().startswith("git "):
            for sub in self.rules.git_block:
                if re.search(rf"\bgit\s+{re.escape(sub)}\b", cmd):
                    return Decision.DENY
            return Decision.ALLOW
        for w in self.rules.network_whitelist:
            if cmd.strip().startswith(w):
                return Decision.ALLOW
        return Decision.ALLOW