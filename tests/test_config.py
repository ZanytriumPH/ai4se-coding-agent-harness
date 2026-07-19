# tests/test_config.py
import re
from harness.config import Config, GuardrailRules, _DEFAULT_ESCAPE_REGEX

def test_config_loads_guardrail_rules(tmp_path):
    cfg_text = r"""
llm_provider: deepseek
memory_path: .agent_memory/
validator:
  max_rounds: 10
  no_progress_window: 3
guardrail:
  deny_paths: [.env, .gitlab-ci.yml]
  deny_path_globs: [".github/**"]
  network_whitelist: [pip install, npm install, mvn verify]
  network_blacklist: [curl, wget, iptables]
  git_block: [push]
  shell_blacklist: ["rm -rf", sudo, "chmod 777", mkfs, DROP, TRUNCATE]
  escape_regex: '(^/)|(\.\.)'
"""
    p = tmp_path / "config.yaml"
    p.write_text(cfg_text, encoding="utf-8")
    cfg = Config.load(str(p))
    assert cfg.validator.max_rounds == 10
    assert cfg.validator.no_progress_window == 3
    assert "rm -rf" in cfg.guardrail.shell_blacklist
    assert "push" in cfg.guardrail.git_block
    assert ".env" in cfg.guardrail.deny_paths


def test_load_omitting_escape_regex_uses_hardened_default(tmp_path):
    # Regression for the latent PR-6 #7 class of bug: Config.load()'s fallback
    # for a yaml WITHOUT escape_regex must equal the GuardrailRules dataclass
    # default (hardened — POSIX abs + .. + Windows drive + UNC). A custom
    # config.yaml that omits the key would otherwise silently fall back to a
    # weaker POSIX-only literal and let C:\ / \\ paths bypass the guardrail.
    # One source of truth: the load() fallback must reference the SAME default
    # as the dataclass field, not a divergent hardcoded string.
    p = tmp_path / "config.yaml"
    p.write_text("llm_provider: deepseek\nmemory_path: m\n", encoding="utf-8")
    cfg = Config.load(str(p))
    # fallback must catch Windows drive AND UNC absolute paths
    assert re.search(cfg.guardrail.escape_regex, "C:\\Users\\x"), \
        "default escape_regex must catch Windows drive paths"
    assert re.search(cfg.guardrail.escape_regex, "\\\\server\\share"), \
        "default escape_regex must catch UNC paths"
    # no drift: load() fallback == dataclass field default
    assert cfg.guardrail.escape_regex == _DEFAULT_ESCAPE_REGEX
    assert GuardrailRules.escape_regex == _DEFAULT_ESCAPE_REGEX