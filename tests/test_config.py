# tests/test_config.py
from harness.config import Config, GuardrailRules

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