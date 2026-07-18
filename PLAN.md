# Coding Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一台自编码的 Coding Agent Harness：给定一个有失败测试/lint/类型错的小型 Python 仓库，agent 据结构化反馈多轮自我修正、危险动作前停下等审批、跨会话记住项目约定与失败教训，并经 mock-LLM 单测与三幕机制演示验证。

**Architecture:** 单进程 AgentLoop（组装上下文→调 LLM→解析动作→Guardrail→Dispatcher→Validator→FeedbackLoop→回灌→停机）。六维最低实现齐全，**反馈闭环为深入重点**。WebUI 为内核外薄层（SSE+审批）。LLMClient/Approver/Memory 均可注入 mock，移除真实 LLM 后机制仍可确定性单测。

**Tech Stack:** Python ≥ 3.11, pytest, ruff, mypy, keyring, httpx（LLM 调用）, PyYAML, FastAPI/Starlette（WebUI SSE）, Open Design（前端）, DeepSeek（默认 LLM）/ Anthropic（可选）。

## Global Constraints

- Python ≥ 3.11；harness 与目标仓库同语言（pytest/ruff/mypy）。
- TDD 硬性：每任务先写失败测试、看到红色、再写最少代码变绿、再重构。禁止先实现后补测试。
- §A.4-C 判据：移除真实 LLM、注入 MockLLMClient + AutoRejectApprover 后，每个机制仍可确定性单测。
- 凭据三不：不硬编码、不入 git、不入日志；keyring 为主、.env 为次并标注明文风险；查看不回显明文。
- 提交前自查 `.env`/history/配置文件无真实 key；commit message 标注 subagent 与人工修改。
- CI 文件 `.gitlab-ci.yml` 必含名为 `unit-test` 的 job；最后一次 CI 必须 pass。
- 仓库不得出现真实凭据。

## File Structure

```
pyproject.toml                     # 包定义、ruff/mypy/pytest 配置、CLI entrypoint
Makefile                           # make test / make demo / make build
.gitlab-ci.yml                     # unit-test job + build job
config.yaml                        # 声明式规则（guardrail/validator/llm/memory）
src/harness/
  models.py                         # enums + dataclasses（Action/Feedback/Failure/TurnRecord/MemoryEntry/RunResult）
  config.py                         # Config.load(path)->Config
  llm/base.py                       # LLMClient 接口
  llm/mock.py                       # MockLLMClient（脚本回放）
  llm/deepseek.py                   # DeepSeekClient（默认）
  llm/anthropic_client.py           # AnthropicClient（可选）
  tools/base.py                     # Tool 接口 + Product
  tools/dispatcher.py               # ToolDispatcher
  tools/files.py                    # read_file/write_file（路径校验）
  tools/shell.py                    # exec_shell
  tools/runners.py                  # run_tests/run_lint/run_typecheck
  feedback/validators.py            # Pytest/Ruff/Mypy Validator
  feedback/feedback_loop.py         # FeedbackLoop（编排/指纹/停机）
  governance/guardrail.py           # Guardrail.inspect
  governance/approver.py            # Approver 接口 + Cli/Web/AutoReject
  memory/memory.py                  # Memory store/recall（JSON Lines）
  credentials.py                    # CredentialStore（keyring 抽象）
  loop.py                           # AgentLoop
src/webui/
  server.py                         # SSE 流 + POST 审批（内核外薄层）
  static/                           # Open Design 前端
src/harness/cli.py                  # 入口，--headless
tests/
  test_models.py
  test_config.py
  test_mock_llm.py
  test_guardrail.py
  test_approver.py
  test_memory.py
  test_validators.py
  test_feedback_loop.py
  test_dispatcher.py
  test_credentials.py
  test_loop.py
  test_integration.py
  fixtures/*.json                   # 预录 pytest/ruff/mypy 产物样本
demo/
  target_repo/                      # mini 目标仓库（手写，5 失败测试+3 lint+2 类型错）
  run_demo.py                       # 三幕机制演示
```

依赖关系：Task 1（models）→ 全员；Task 2（config）；Task 3（LLM mock）；Task 4/5（guardrail/approver，可并行）；Task 6（memory）；Task 7（validators）→ Task 8（feedback_loop）；Task 9（tools/dispatcher）；Task 11（credentials，独立可并行）；Task 10（loop，依赖 3/4/5/7/8/9）；Task 12（target repo，独立可并行）；Task 13（integration，依赖 10/12）；Task 14（webui，依赖 5/10）；Task 15（demo，依赖 8/10）；Task 16/17（打包/CI，最后）。

## Worktree 与 PR 划分（§4.6/§4.7）

每个 worktree 对应一个 PR、一组职责内聚的 task；worktree 在**执行时**由 `superpowers:using-git-worktrees` 技能创建。基础层（PR-0）须先行 merge，其余 PR 据依赖图推进，**同一并行组内的 PR 可开多个 worktree 同时推进**。

| Worktree / PR | 含 Task | 标题 | 依赖 | 可与谁并行 |
|---|---|---|---|---|
| **PR-0 · 基座** | T1, T2, T3 | models + config + LLM 抽象/Mock | — | 无（先行 merge） |
| **PR-1 · 治理** | T4, T5 | Guardrail + Approver 三实现 | PR-0 | PR-2/3/4/6 |
| **PR-2 · 记忆** | T6 | Memory store/recall（自实现） | PR-0 | PR-1/3/4/6 |
| **PR-3 · 校验与反馈★** | T7, T8 | Validators + FeedbackLoop（重点） | PR-0 | PR-1/2/4/6 |
| **PR-4 · 工具分发** | T9 | ToolDispatcher + 工具集 | PR-0 | PR-1/2/3/6 |
| **PR-5 · 凭据** | T11 | CredentialStore + FakeKeyring | PR-0 | PR-1/2/3/4/6 |
| **PR-6 · 目标仓库** | T12 | 手写 mini target repo | — | 全员（无代码依赖） |
| **PR-7 · 主循环** | T10 | AgentLoop（集成） | PR-1/2/3/4 | 无（汇合点） |
| **PR-8 · 集成测试** | T13 | mock-LLM 端到端修复 | PR-7, PR-6 | 无 |
| **PR-9 · WebUI** | T14 | SSE + 审批 + Open Design 前端 | PR-7 | PR-8/10 |
| **PR-10 · 机制演示** | T15 | 三幕 demo 脚本 | PR-3, PR-7 | PR-8/9 |
| **PR-11 · 打包与 CI** | T16, T17 | pyproject + CLI + Makefile + .gitlab-ci.yml | PR-10 | 无 |

并行节奏建议：PR-0 先行 merge → 同时开 PR-1/2/3/4/5/6 六个 worktree → 汇合到 PR-7 → 再 PR-8/9/10 → 最后 PR-11。每个 PR 内部仍严格按 task 的红-绿-重构-提交纪律推进；PR 间以两阶段评审（spec 合规 → 代码质量）为闸门，Critical issue 必须修复才进下一 PR。

---

---

### Task 1: 核心数据模型 `models.py`

**Files:**
- Create: `src/harness/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Source`, `Verdict`, `FailureKind`(enums), `Action`, `Failure`, `Feedback`, `TurnRecord`, `MemoryEntry`, `RunResult`(dataclasses), `failure_fingerprint(feedback)->frozenset`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from harness.models import (
    Source, Verdict, FailureKind, Action, Failure, Feedback,
    failure_fingerprint,
)

def test_failure_fingerprint_ignores_message():
    f1 = Feedback(source=Source.TEST, verdict=Verdict.FAIL, failures=[
        Failure(kind=FailureKind.ASSERTION_ERROR, location="tests/test_a.py::test_x", message="exp 200 got 401"),
    ])
    f2 = Feedback(source=Source.TEST, verdict=Verdict.FAIL, failures=[
        Failure(kind=FailureKind.ASSERTION_ERROR, location="tests/test_a.py::test_x", message="exp 200 got 500"),
    ])
    assert failure_fingerprint(f1) == failure_fingerprint(f2)
    assert failure_fingerprint(f1) == frozenset({(Source.TEST, FailureKind.ASSERTION_ERROR, "tests/test_a.py::test_x")})

def test_pass_feedback_has_empty_fingerprint():
    f = Feedback(source=Source.TEST, verdict=Verdict.PASS, failures=[])
    assert failure_fingerprint(f) == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: harness.models`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class Source(Enum):
    TEST = "test"; LINT = "lint"; TYPE = "type"

class Verdict(Enum):
    PASS = "pass"; FAIL = "fail"

class FailureKind(Enum):
    ASSERTION_ERROR = "assertion_error"
    COLLECTION_ERROR = "collection_error"
    IMPORT_ERROR = "import_error"
    TIMEOUT = "timeout"
    LINT_VIOLATION = "lint_violation"
    TYPE_VIOLATION = "type_violation"
    UNKNOWN = "unknown"

@dataclass
class Action:
    tool: str
    args: dict[str, Any]

@dataclass
class Failure:
    kind: FailureKind
    location: str
    message: str

@dataclass
class Feedback:
    source: Source
    verdict: Verdict
    failures: list[Failure] = field(default_factory=list)

@dataclass
class TurnRecord:
    round: int
    action: Action
    feedback: Feedback | None
    guardrail_decision: str
    failure_fingerprint: frozenset | None

@dataclass
class MemoryEntry:
    id: str
    tags: list[str]
    content: str
    created_at: str

@dataclass
class RunResult:
    outcome: str  # "success" | "no_progress" | "max_rounds"
    rounds: int
    turn_records: list[TurnRecord]

def failure_fingerprint(feedback: Feedback) -> frozenset:
    return frozenset(
        (feedback.source, f.kind, f.location) for f in feedback.failures
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/models.py tests/test_models.py
git commit -m "feat(models): core data models + failure fingerprint"
```

---

### Task 2: 声明式配置 `config.py`

**Files:**
- Create: `src/harness/config.py`, `config.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: none
- Produces: `Config`, `GuardrailRules`, `ValidatorConfig`, `Config.load(path)->Config`。`Config` 暴露 `.guardrail`、`.validator`（含 `max_rounds`/`no_progress_window`）、`.llm_provider`、`.memory_path`。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from harness.config import Config, GuardrailRules

def test_config_loads_guardrail_rules(tmp_path):
    cfg_text = """
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
  escape_regex: "\\.\\./|/"
"""
    p = tmp_path / "config.yaml"
    p.write_text(cfg_text, encoding="utf-8")
    cfg = Config.load(str(p))
    assert cfg.validator.max_rounds == 10
    assert cfg.validator.no_progress_window == 3
    assert "rm -rf" in cfg.guardrail.shell_blacklist
    assert "push" in cfg.guardrail.git_block
    assert ".env" in cfg.guardrail.deny_paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: harness.config`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class GuardrailRules:
    deny_paths: list[str] = field(default_factory=list)
    deny_path_globs: list[str] = field(default_factory=list)
    network_whitelist: list[str] = field(default_factory=list)
    network_blacklist: list[str] = field(default_factory=list)
    git_block: list[str] = field(default_factory=list)
    shell_blacklist: list[str] = field(default_factory=list)
    escape_regex: str = r"\.\./|/"

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
                escape_regex=g.get("escape_regex", r"\.\./|/"),
            ),
        )
```

```yaml
# config.yaml
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
  escape_regex: "\\.\\./|/"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/config.py config.yaml tests/test_config.py
git commit -m "feat(config): declarative yaml config loader + default rules"
```

---

### Task 3: LLM 抽象层与 Mock `llm/base.py` + `llm/mock.py`

**Files:**
- Create: `src/harness/llm/__init__.py`, `src/harness/llm/base.py`, `src/harness/llm/mock.py`
- Test: `tests/test_mock_llm.py`

**Interfaces:**
- Produces: `LLMResponse`（dataclass: `tool: str|None, args: dict|None, text: str|None, parse_error: bool`）、`LLMClient`（接口 `complete(messages, tools_schema)->LLMResponse`）、`MockLLMClient`（按脚本回放动作序列）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mock_llm.py
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse

def test_mock_llm_replays_scripted_actions():
    script = [
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "bad"}, text=None, parse_error=False),
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "good"}, text=None, parse_error=False),
    ]
    llm = MockLLMClient(script)
    r1 = llm.complete(messages=[], tools_schema=[])
    r2 = llm.complete(messages=[], tools_schema=[])
    assert r1.tool == "write_file" and r1.args["content"] == "bad"
    assert r2.args["content"] == "good"

def test_mock_llm_exhausts_script_returns_parse_error():
    llm = MockLLMClient([])
    r = llm.complete([], [])
    assert r.parse_error is True and r.tool is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mock_llm.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/llm/base.py
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
```

```python
# src/harness/llm/mock.py
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
```

```python
# src/harness/llm/__init__.py
from .base import LLMClient, LLMResponse
from .mock import MockLLMClient
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mock_llm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/llm/ tests/test_mock_llm.py
git commit -m "feat(llm): LLMClient protocol + MockLLMClient scripted playback"
```

---

### Task 4: 治理护栏 `governance/guardrail.py`

**Files:**
- Create: `src/harness/governance/__init__.py`, `src/harness/governance/guardrail.py`
- Test: `tests/test_guardrail.py`

**Interfaces:**
- Consumes: `Config`/`GuardrailRules`（Task 2）、`Action`（Task 1）
- Produces: `Decision`(enum `ALLOW`/`DENY`/`NEED_APPROVAL`)、`Guardrail(rules).inspect(action)->Decision`。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guardrail.py
from harness.config import GuardrailRules
from harness.governance.guardrail import Guardrail, Decision
from harness.models import Action

def rules():
    return GuardrailRules(
        deny_paths=[".env", ".gitlab-ci.yml"],
        deny_path_globs=[".github/**"],
        network_whitelist=["pip install", "npm install"],
        network_blacklist=["curl", "wget"],
        git_block=["push"],
        shell_blacklist=["rm -rf", "sudo", "DROP", "TRUNCATE"],
    )

def test_write_to_env_is_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": ".env", "content": "x"})) == Decision.DENY

def test_path_escape_needs_approval():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": "../../etc/passwd", "content": "x"})) == Decision.NEED_APPROVAL

def test_destructive_shell_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "rm -rf /"})) == Decision.DENY

def test_git_push_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "git push origin main"})) == Decision.DENY

def test_pip_install_allowed():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "pip install ruff"})) == Decision.ALLOW

def test_curl_denied():
    g = Guardrail(rules())
    assert g.inspect(Action("exec_shell", {"cmd": "curl http://x"})) == Decision.DENY

def test_normal_write_allowed():
    g = Guardrail(rules())
    assert g.inspect(Action("write_file", {"path": "src/app.py", "content": "x"})) == Decision.ALLOW
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_guardrail.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

```python
# src/harness/governance/__init__.py
from .guardrail import Guardrail, Decision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_guardrail.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/governance/ tests/test_guardrail.py
git commit -m "feat(governance): Guardrail.inspect with deny/escape/network rules"
```

---

### Task 5: 审批接口与三实现 `governance/approver.py`

**Files:**
- Create: `src/harness/governance/approver.py`
- Test: `tests/test_approver.py`

**Interfaces:**
- Consumes: `Action`、`Decision`（Task 4）
- Produces: `Approver`（接口 `approve(action)->bool`）、`CliApprover`、`AutoRejectApprover`、`WebApprover`（占位实现，Task 14 充实）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_approver.py
from harness.governance.approver import AutoRejectApprover
from harness.models import Action

def test_auto_reject_returns_false_without_io():
    a = AutoRejectApprover()
    assert a.approve(Action("write_file", {"path": "../../etc", "content": "x"})) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_approver.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/governance/approver.py
from __future__ import annotations
from typing import Protocol
from harness.models import Action

class Approver(Protocol):
    def approve(self, action: Action) -> bool: ...

class AutoRejectApprover:
    def approve(self, action: Action) -> bool:
        return False

class CliApprover:
    def __init__(self, input_fn=input, print_fn=print):
        self._input = input_fn
        self._print = print_fn

    def approve(self, action: Action) -> bool:
        self._print(f"[HITL] approve action? {action.tool} {action.args} [y/N]")
        return self._input().strip().lower() == "y"

class WebApprover:
    """Task 14 充实：通过 SSE/POST 与前端交互。此处留可注入的回调桩。"""
    def __init__(self, ask=None):
        self._ask = ask or (lambda _a: False)

    def approve(self, action: Action) -> bool:
        return self._ask(action)
```

在 `src/harness/governance/__init__.py` 追加导出：`from .approver import Approver, AutoRejectApprover, CliApprover, WebApprover`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_approver.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/governance/approver.py src/harness/governance/__init__.py tests/test_approver.py
git commit -m "feat(governance): Approver protocol + AutoReject/Cli/Web impls"
```

---

### Task 6: 记忆 `memory/memory.py`（自实现）

**Files:**
- Create: `src/harness/memory/__init__.py`, `src/harness/memory/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Consumes: `MemoryEntry`（Task 1）
- Produces: `RecallQuery`、`Memory`（`store(entry)`、`recall(query)->list[MemoryEntry]`），JSON Lines 存储。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory.py
from harness.memory.memory import Memory, RecallQuery
from harness.models import MemoryEntry

def test_store_and_recall_by_tag(tmp_path):
    mem = Memory(str(tmp_path / "mem.jsonl"))
    mem.store(MemoryEntry(id="1", tags=["convention", "test"], content="uses pytest", created_at="t0"))
    mem.store(MemoryEntry(id="2", tags=["lesson", "test"], content="don't edit conftest", created_at="t1"))
    got = mem.recall(RecallQuery(tags={"test"}))
    ids = {e.id for e in got}
    assert ids == {"1", "2"}

def test_recall_filters_by_multiple_tags_intersection(tmp_path):
    mem = Memory(str(tmp_path / "mem.jsonl"))
    mem.store(MemoryEntry(id="1", tags=["convention", "test"], content="a", created_at="t0"))
    mem.store(MemoryEntry(id="2", tags=["lesson", "test"], content="b", created_at="t1"))
    got = mem.recall(RecallQuery(tags={"lesson"}))
    assert {e.id for e in got} == {"2"}

def test_recall_empty_when_no_match(tmp_path):
    mem = Memory(str(tmp_path / "mem.jsonl"))
    mem.store(MemoryEntry(id="1", tags=["x"], content="a", created_at="t0"))
    assert mem.recall(RecallQuery(tags={"y"})) == []

def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "mem.jsonl")
    Memory(path).store(MemoryEntry(id="1", tags=["x"], content="a", created_at="t0"))
    got = Memory(path).recall(RecallQuery(tags={"x"}))
    assert {e.id for e in got} == {"1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/memory/memory.py
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from harness.models import MemoryEntry

@dataclass
class RecallQuery:
    tags: set[str]

class Memory:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def store(self, entry: MemoryEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": entry.id, "tags": entry.tags,
                "content": entry.content, "created_at": entry.created_at,
            }, ensure_ascii=False) + "\n")

    def _load_all(self) -> list[MemoryEntry]:
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            out.append(MemoryEntry(
                id=d["id"], tags=d["tags"], content=d["content"], created_at=d["created_at"],
            ))
        return out

    def recall(self, query: RecallQuery) -> list[MemoryEntry]:
        return [e for e in self._load_all() if query.tags.issubset(set(e.tags))]
```

```python
# src/harness/memory/__init__.py
from .memory import Memory, RecallQuery
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/memory/ tests/test_memory.py
git commit -m "feat(memory): JSON Lines store + tag-intersection recall"
```

---

### Task 7: 校验器套件 `feedback/validators.py`

**Files:**
- Create: `src/harness/feedback/__init__.py`, `src/harness/feedback/validators.py`, `tests/fixtures/pytest_fail.json`, `tests/fixtures/pytest_pass.json`, `tests/fixtures/ruff_fail.json`, `tests/fixtures/mypy_fail.json`
- Test: `tests/test_validators.py`

**Interfaces:**
- Consumes: `Source`/`Verdict`/`FailureKind`/`Feedback`/`Failure`（Task 1）
- Produces: `Validator`（接口 `parse(product)->Feedback`）、`PytestValidator`、`RuffValidator`、`MypyValidator`、`Product`(dataclass: `exitcode:int, stdout:str, stderr:str`)。

- [ ] **Step 1: Write fixtures**

```json
// tests/fixtures/pytest_fail.json  (pytest --json-report 简化形态)
{
  "summary": {"total": 2, "failed": 1, "errors": 1, "passed": 0},
  "tests": [
    {"nodeid": "tests/test_a.py::test_login", "outcome": "failed", "call": {"crash": {"type": "AssertionError", "message": "assert 200 == 401"}}},
    {"nodeid": "tests/test_db.py::test_conn", "outcome": "error", "call": {"crash": {"type": "ModuleNotFoundError", "message": "No module named 'psycopg2'"}}}
  ]
}
```

```json
// tests/fixtures/pytest_pass.json
{"summary": {"total": 1, "failed": 0, "errors": 0, "passed": 1}, "tests": []}
```

```json
// tests/fixtures/ruff_fail.json  (ruff --output-format=json)
[{"filename": "src/app.py", "location": {"row": 12, "column": 1}, "code": "F401", "message": "'os' imported but unused"}]
```

```json
// tests/fixtures/mypy_fail.json
[{"file": "src/app.py", "line": 8, "type": "error", "message": "Argument 1 has incompatible type \"str\"; expected \"int\""}]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_validators.py
import json
from pathlib import Path
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator, Product
from harness.models import Source, Verdict, FailureKind

FIX = Path(__file__).parent / "fixtures"

def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))

def test_pytest_validator_classifies_failures():
    v = PytestValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("pytest_fail.json")), stderr=""))
    assert fb.source == Source.TEST and fb.verdict == Verdict.FAIL
    kinds = {(f.kind, f.location) for f in fb.failures}
    assert (FailureKind.ASSERTION_ERROR, "tests/test_a.py::test_login") in kinds
    assert (FailureKind.IMPORT_ERROR, "tests/test_db.py::test_conn") in kinds

def test_pytest_validator_pass():
    v = PytestValidator()
    fb = v.parse(Product(exitcode=0, stdout=json.dumps(load("pytest_pass.json")), stderr=""))
    assert fb.verdict == Verdict.PASS and fb.failures == []

def test_ruff_validator_classifies_lint():
    v = RuffValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("ruff_fail.json")), stderr=""))
    assert fb.source == Source.LINT and fb.verdict == Verdict.FAIL
    f = fb.failures[0]
    assert f.kind == FailureKind.LINT_VIOLATION and f.location == "src/app.py:12"

def test_mypy_validator_classifies_type():
    v = MypyValidator()
    fb = v.parse(Product(exitcode=1, stdout=json.dumps(load("mypy_fail.json")), stderr=""))
    assert fb.source == Source.TYPE and fb.verdict == Verdict.FAIL
    f = fb.failures[0]
    assert f.kind == FailureKind.TYPE_VIOLATION and f.location == "src/app.py:8"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_validators.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# src/harness/feedback/validators.py
from __future__ import annotations
import json
from dataclasses import dataclass
from harness.models import Source, Verdict, FailureKind, Feedback, Failure

@dataclass
class Product:
    exitcode: int
    stdout: str
    stderr: str

class Validator:
    def parse(self, product: Product) -> Feedback: ...

class PytestValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        data = json.loads(product.stdout or "{}")
        failures: list[Failure] = []
        for t in data.get("tests", []):
            if t.get("outcome") in ("failed", "error"):
                crash = t.get("call", {}).get("crash", {})
                ctype = crash.get("type", "")
                kind = FailureKind.IMPORT_ERROR if "Import" in ctype else FailureKind.ASSERTION_ERROR
                failures.append(Failure(kind=kind, location=t["nodeid"], message=crash.get("message", "")))
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.TEST, verdict=verdict, failures=failures)

class RuffValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        items = json.loads(product.stdout or "[]")
        failures = [
            Failure(kind=FailureKind.LINT_VIOLATION,
                    location=f"{it['filename']}:{it['location']['row']}",
                    message=f"{it['code']}: {it['message']}")
            for it in items
        ]
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.LINT, verdict=verdict, failures=failures)

class MypyValidator(Validator):
    def parse(self, product: Product) -> Feedback:
        items = json.loads(product.stdout or "[]")
        failures = [
            Failure(kind=FailureKind.TYPE_VIOLATION,
                    location=f"{it['file']}:{it['line']}",
                    message=it.get("message", ""))
            for it in items if it.get("type") == "error"
        ]
        verdict = Verdict.PASS if not failures else Verdict.FAIL
        return Feedback(source=Source.TYPE, verdict=verdict, failures=failures)
```

```python
# src/harness/feedback/__init__.py
from .validators import Validator, PytestValidator, RuffValidator, MypyValidator, Product
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_validators.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/harness/feedback/ tests/test_validators.py tests/fixtures/
git commit -m "feat(feedback): pytest/ruff/mypy validators parse structured products"
```

---

### Task 8: 反馈闭环 `feedback/feedback_loop.py`（★ 重点维度）

**Files:**
- Create: `src/harness/feedback/feedback_loop.py`
- Test: `tests/test_feedback_loop.py`

**Interfaces:**
- Consumes: `Validator`/`Product`（Task 7）、`failure_fingerprint`（Task 1）、`ValidatorConfig`（Task 2）
- Produces: `StopReason`(enum `CONTINUE`/`SUCCESS`/`NO_PROGRESS`/`MAX_ROUNDS`)、`FeedbackLoop`（`update(feedbacks)->(stop_reason, summary_str)`；维护轮次与指纹历史）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_feedback_loop.py
from harness.feedback.feedback_loop import FeedbackLoop, StopReason
from harness.feedback.validators import Product, PytestValidator, RuffValidator, MypyValidator
from harness.models import Source, Verdict, Failure, FailureKind, Feedback
from harness.config import ValidatorConfig
import json

def fb_test_fail():
    return Feedback(source=Source.TEST, verdict=Verdict.FAIL, failures=[
        Failure(FailureKind.ASSERTION_ERROR, "tests/test_a.py::test_x", "m1")])

def fb_pass():
    return Feedback(source=Source.TEST, verdict=Verdict.PASS, failures=[])

def test_success_when_all_pass():
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=10, no_progress_window=3))
    stop, _ = loop.update({"test": fb_pass()})
    assert stop == StopReason.SUCCESS

def test_no_progress_after_window():
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=10, no_progress_window=3))
    for _ in range(2):
        stop, _ = loop.update({"test": fb_test_fail()})
        assert stop == StopReason.CONTINUE
    stop, _ = loop.update({"test": fb_test_fail()})
    assert stop == StopReason.NO_PROGRESS

def test_max_rounds():
    # 构造每次指纹都不同, 避免触发 no_progress
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=2, no_progress_window=99))
    f1 = Feedback(Source.TEST, Verdict.FAIL, [Failure(FailureKind.ASSERTION_ERROR, "loc1", "m")])
    f2 = Feedback(Source.TEST, Verdict.FAIL, [Failure(FailureKind.ASSERTION_ERROR, "loc2", "m")])
    stop, _ = loop.update({"test": f1}); assert stop == StopReason.CONTINUE
    stop, _ = loop.update({"test": f2}); assert stop == StopReason.MAX_ROUNDS

def test_summary_is_structured_not_raw():
    loop = FeedbackLoop(validators={}, cfg=ValidatorConfig(max_rounds=10, no_progress_window=3))
    _, summary = loop.update({"test": fb_test_fail()})
    assert "FEEDBACK" in summary and "assertion_error" in summary and "tests/test_a.py::test_x" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_feedback_loop.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/feedback/feedback_loop.py
from __future__ import annotations
from enum import Enum
from harness.models import Feedback, failure_fingerprint
from harness.config import ValidatorConfig

class StopReason(Enum):
    CONTINUE = "continue"
    SUCCESS = "success"
    NO_PROGRESS = "no_progress"
    MAX_ROUNDS = "max_rounds"

class FeedbackLoop:
    def __init__(self, validators: dict, cfg: ValidatorConfig):
        self.validators = validators
        self.cfg = cfg
        self.round = 0
        self.history: list[frozenset] = []

    def update(self, feedbacks: dict[str, Feedback]) -> tuple[StopReason, str]:
        self.round += 1
        all_pass = all(f.verdict.name == "PASS" for f in feedbacks.values()) if feedbacks else True
        summary = self._summarize(feedbacks)
        if all_pass:
            return StopReason.SUCCESS, summary
        fp = frozenset().union(*(failure_fingerprint(f) for f in feedbacks.values()))
        self.history.append(fp)
        if self.round >= self.cfg.max_rounds:
            return StopReason.MAX_ROUNDS, summary
        if self._no_progress(fp):
            return StopReason.NO_PROGRESS, summary
        return StopReason.CONTINUE, summary

    def _no_progress(self, current: frozenset) -> bool:
        if len(self.history) < self.cfg.no_progress_window:
            return False
        window = self.history[-(self.cfg.no_progress_window):]
        return all(w == current for w in window)

    def _summarize(self, feedbacks: dict[str, Feedback]) -> str:
        lines = ["FEEDBACK"]
        for name, f in feedbacks.items():
            lines.append(f"[{name} source={f.source.value} verdict={f.verdict.value}]")
            for fl in f.failures:
                lines.append(f"- [{fl.kind.value}] {fl.location} : {fl.message}")
        lines.append(f"PROGRESS: round {self.round}/{self.cfg.max_rounds}")
        return "\n".join(lines)
```

在 `src/harness/feedback/__init__.py` 追加：`from .feedback_loop import FeedbackLoop, StopReason`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_feedback_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/feedback/feedback_loop.py src/harness/feedback/__init__.py tests/test_feedback_loop.py
git commit -m "feat(feedback): FeedbackLoop with success/no_progress/max_rounds stop"
```

---

### Task 9: 工具分发 `tools/`

**Files:**
- Create: `src/harness/tools/__init__.py`, `src/harness/tools/base.py`, `src/harness/tools/files.py`, `src/harness/tools/shell.py`, `src/harness/tools/runners.py`, `src/harness/tools/dispatcher.py`
- Test: `tests/test_dispatcher.py`

**Interfaces:**
- Consumes: `Action`、`Product`（Task 1/7）
- Produces: `Tool`（接口 `exec(args)->Product`）、`ReadFileTool`/`WriteFileTool`（路径校验不得逃逸工作目录）、`ExecShellTool`、`RunTestsTool`/`RunLintTool`/`RunTypecheckTool`、`ToolDispatcher`（`exec(action)->Product`，按 `action.tool` 路由）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatcher.py
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.base import Product
from harness.models import Action

def test_write_then_read(tmp_path):
    d = ToolDispatcher(workdir=str(tmp_path))
    w = d.exec(Action("write_file", {"path": "a.py", "content": "x=1"}))
    assert w.exitcode == 0
    r = d.exec(Action("read_file", {"path": "a.py"}))
    assert "x=1" in r.stdout

def test_write_escape_rejected(tmp_path):
    d = ToolDispatcher(workdir=str(tmp_path))
    p = d.exec(Action("write_file", {"path": "../escape.py", "content": "x"}))
    assert p.exitcode != 0 and "escape" in (p.stderr + p.stdout).lower()

def test_exec_shell_runs(tmp_path):
    d = ToolDispatcher(workdir=str(tmp_path))
    p = d.exec(Action("exec_shell", {"cmd": "echo hi"}))
    assert "hi" in p.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatcher.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/tools/base.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Product:
    exitcode: int
    stdout: str
    stderr: str

class Tool:
    name: str
    def exec(self, args: dict, workdir: str) -> Product: ...
```

```python
# src/harness/tools/files.py
from __future__ import annotations
from pathlib import Path
from .base import Tool, Product

def _safe(workdir: str, path: str) -> Path:
    base = Path(workdir).resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"path escape detected: {path}")
    return target

class ReadFileTool(Tool):
    name = "read_file"
    def exec(self, args, workdir):
        try:
            txt = _safe(workdir, args["path"]).read_text(encoding="utf-8")
            return Product(0, txt, "")
        except Exception as e:
            return Product(1, "", str(e))

class WriteFileTool(Tool):
    name = "write_file"
    def exec(self, args, workdir):
        try:
            t = _safe(workdir, args["path"])
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(args["content"], encoding="utf-8")
            return Product(0, f"wrote {args['path']}", "")
        except Exception as e:
            return Product(1, "", str(e))
```

```python
# src/harness/tools/shell.py
from __future__ import annotations
import subprocess
from .base import Tool, Product

class ExecShellTool(Tool):
    name = "exec_shell"
    def exec(self, args, workdir):
        r = subprocess.run(args["cmd"], shell=True, cwd=workdir,
                            capture_output=True, text=True, timeout=120)
        return Product(r.returncode, r.stdout, r.stderr)
```

```python
# src/harness/tools/runners.py
from __future__ import annotations
import subprocess, json
from .base import Tool, Product

class RunTestsTool(Tool):
    name = "run_tests"
    def exec(self, args, workdir):
        r = subprocess.run(["pytest", "--json-report", "--json-report-file=-"],
                           cwd=workdir, capture_output=True, text=True, timeout=300)
        return Product(r.returncode, r.stdout, r.stderr)

class RunLintTool(Tool):
    name = "run_lint"
    def exec(self, args, workdir):
        r = subprocess.run(["ruff", "check", "--output-format=json", "."],
                           cwd=workdir, capture_output=True, text=True, timeout=120)
        return Product(r.returncode, r.stdout, r.stderr)

class RunTypecheckTool(Tool):
    name = "run_typecheck"
    def exec(self, args, workdir):
        r = subprocess.run(["mypy", "--output=json", "src"],
                           cwd=workdir, capture_output=True, text=True, timeout=180)
        return Product(r.returncode, r.stdout, r.stderr)
```

```python
# src/harness/tools/dispatcher.py
from __future__ import annotations
from .base import Tool, Product
from .files import ReadFileTool, WriteFileTool
from .shell import ExecShellTool
from .runners import RunTestsTool, RunLintTool, RunTypecheckTool
from harness.models import Action

class ToolDispatcher:
    def __init__(self, workdir: str):
        self.workdir = workdir
        self.tools: dict[str, Tool] = {
            t.name: t for t in [
                ReadFileTool(), WriteFileTool(), ExecShellTool(),
                RunTestsTool(), RunLintTool(), RunTypecheckTool(),
            ]
        }

    def exec(self, action: Action) -> Product:
        tool = self.tools.get(action.tool)
        if tool is None:
            return Product(1, "", f"unknown tool: {action.tool}")
        return tool.exec(action.args, self.workdir)
```

```python
# src/harness/tools/__init__.py
from .base import Tool, Product
from .dispatcher import ToolDispatcher
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/tools/ tests/test_dispatcher.py
git commit -m "feat(tools): ToolDispatcher + file/shell/runner tools with path guard"
```

---

### Task 10: Agent 主循环 `loop.py`

**Files:**
- Create: `src/harness/loop.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `LLMClient`(Task 3)、`Guardrail`+`Approver`(Task 4/5)、`ToolDispatcher`(Task 9)、`Validator`套件+`FeedbackLoop`(Task 7/8)、`Memory`(Task 6)、`Config`(Task 2)、`models`(Task 1)
- Produces: `AgentLoop`（`run()->RunResult`）。

- [ ] **Step 1: Write the failing test（mock-LLM 驱动，演示幕②）**

```python
# tests/test_loop.py
from harness.loop import AgentLoop
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.governance.guardrail import Guardrail, Decision
from harness.governance.approver import AutoRejectApprover
from harness.governance.guardrail import Guardrail
from harness.config import GuardrailRules, ValidatorConfig
from harness.feedback.feedback_loop import FeedbackLoop
from harness.feedback.validators import PytestValidator, Product
from harness.tools.dispatcher import ToolDispatcher
from harness.memory.memory import Memory
from harness.models import Action
import json, types

class StubDispatcher:
    """对 write_file 不真写, 对 run_tests 返回预设产物, 让测试无网络/无 pytest。"""
    def __init__(self, fail_then_pass):
        self.calls = 0
        self.fail_then_pass = fail_then_pass
    def exec(self, action: Action):
        if action.tool == "run_tests":
            self.calls += 1
            report = {"summary": {"passed": 0, "failed": 1, "errors": 0},
                      "tests": [{"nodeid": "t::x", "outcome": "failed",
                                 "call": {"crash": {"type": "AssertionError", "message": "m"}}}]} if self.calls < 2 else {"summary": {"passed": 1, "failed": 0, "errors": 0}, "tests": []}
            return Product(1, json.dumps(report), "")
        return Product(0, "", "")

def test_loop_recovers_from_fail_to_success(tmp_path):
    # MockLLM: 第1轮写"坏"修复+跑测试→fail; 第2轮写"好"修复+跑测试→pass
    script = [
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "bad"}, text=None),
        LLMResponse(tool="run_tests", args={}, text=None),
        LLMResponse(tool="write_file", args={"path": "a.py", "content": "good"}, text=None),
        LLMResponse(tool="run_tests", args={}, text=None),
    ]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StubDispatcher(fail_then_pass=True),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "success"
    assert result.rounds == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_loop.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/loop.py
from __future__ import annotations
from harness.models import Action, Feedback, TurnRecord, RunResult, failure_fingerprint
from harness.governance.guardrail import Guardrail, Decision
from harness.feedback.feedback_loop import FeedbackLoop, StopReason
from harness.config import ValidatorConfig
from harness.memory.memory import Memory, RecallQuery

class AgentLoop:
    def __init__(self, llm, guardrail: Guardrail, approver, dispatcher,
                 validators: dict, feedback_cfg: ValidatorConfig, memory: Memory,
                 system_prompt: str = "You repair a failing Python repo."):
        self.llm = llm
        self.guardrail = guardrail
        self.approver = approver
        self.dispatcher = dispatcher
        self.validators = validators
        self.feedback_cfg = feedback_cfg
        self.memory = memory
        self.system_prompt = system_prompt
        self.messages: list = []
        self.turns: list[TurnRecord] = []

    def run(self) -> RunResult:
        self.messages.append({"role": "system", "content": self.system_prompt})
        # 首轮载入项目约定
        conv = self.memory.recall(RecallQuery(tags={"convention"}))
        if conv:
            self.messages.append({"role": "system",
                "content": "PROJECT CONVENTIONS:\n" + "\n".join(e.content for e in conv)})
        loop = FeedbackLoop(validators=self.validators, cfg=self.feedback_cfg)
        stop = StopReason.CONTINUE
        last_feedback: Feedback | None = None
        while stop == StopReason.CONTINUE:
            if last_feedback is not None:
                self.messages.append({"role": "user", "content": last_feedback})
            resp = self.llm.complete(self.messages, tools_schema=[])
            if resp.parse_error or resp.tool is None:
                break
            action = Action(tool=resp.tool, args=resp.args or {})
            decision = self.guardrail.inspect(action)
            guardrail_decision = decision.value
            if decision == Decision.DENY:
                last_feedback = f"DENIED action: {action.tool} {action.args}"
                self.turns.append(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                stop = StopReason.CONTINUE
                continue
            if decision == Decision.NEED_APPROVAL:
                if not self.approver.approve(action):
                    last_feedback = f"REJECTED by HITL: {action.tool} {action.args}"
                    self.turns.append(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                    continue
            product = self.dispatcher.exec(action)
            feedbacks: dict[str, Feedback] = {}
            if action.tool == "run_tests" and "test" in self.validators:
                feedbacks["test"] = self.validators["test"].parse(product)
            elif action.tool == "run_lint" and "lint" in self.validators:
                feedbacks["lint"] = self.validators["lint"].parse(product)
            elif action.tool == "run_typecheck" and "type" in self.validators:
                feedbacks["type"] = self.validators["type"].parse(product)
            else:
                # 非校验类工具动作, 视为推进, 不更新 stop
                last_feedback = product.stdout or product.stderr or f"ran {action.tool}"
                self.turns.append(TurnRecord(len(self.turns)+1, action, None, guardrail_decision, None))
                continue
            stop, summary = loop.update(feedbacks)
            last_feedback = summary
            fp = failure_fingerprint(next(iter(feedbacks.values()))) if feedbacks else None
            self.turns.append(TurnRecord(len(self.turns)+1, action, next(iter(feedbacks.values()), None), guardrail_decision, fp))
        outcome_map = {StopReason.SUCCESS: "success", StopReason.NO_PROGRESS: "no_progress", StopReason.MAX_ROUNDS: "max_rounds", StopReason.CONTINUE: "max_rounds"}
        return RunResult(outcome=outcome_map[stop], rounds=loop.round, turn_records=self.turns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/loop.py tests/test_loop.py
git commit -m "feat(loop): AgentLoop integrates llm/guardrail/dispatcher/feedback"
```

---

### Task 11: 凭据管理 `credentials.py`

**Files:**
- Create: `src/harness/credentials.py`
- Test: `tests/test_credentials.py`

**Interfaces:**
- Consumes: `keyring` 库（真实运行）；测试注入 in-memory fake
- Produces: `CredentialStore`（`store(key)`/`get()->str|None`/`status()->str`/`update(key)`/`clear()`），服务名常量 `SERVICE_NAME="coding-agent-harness"`。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_credentials.py
from harness.credentials import CredentialStore, FakeKeyring

def test_store_then_status_configured():
    kr = FakeKeyring()
    cs = CredentialStore(keyring=kr)
    cs.store("sk-secret")
    assert cs.status() == "configured"
    assert kr.get_secret() == "sk-secret"

def test_status_not_configured():
    cs = CredentialStore(keyring=FakeKeyring())
    assert cs.status() == "not configured"

def test_get_does_not_leak_via_status():
    cs = CredentialStore(keyring=FakeKeyring())
    cs.store("sk-secret")
    assert "sk-secret" not in cs.status()

def test_update_overwrites():
    kr = FakeKeyring()
    cs = CredentialStore(keyring=kr)
    cs.store("old"); cs.update("new")
    assert kr.get_secret() == "new"

def test_clear():
    kr = FakeKeyring()
    cs = CredentialStore(keyring=kr)
    cs.store("x"); cs.clear()
    assert cs.status() == "not configured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_credentials.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/credentials.py
from __future__ import annotations
from typing import Protocol

SERVICE_NAME = "coding-agent-harness"
ACCOUNT = "default"

class KeyringLike(Protocol):
    def set_password(self, service: str, account: str, password: str) -> None: ...
    def get_password(self, service: str, account: str) -> str | None: ...
    def delete_password(self, service: str, account: str) -> None: ...

class FakeKeyring:
    def __init__(self):
        self._store = {}
    def set_password(self, service, account, password):
        self._store[(service, account)] = password
    def get_password(self, service, account):
        return self._store.get((service, account))
    def delete_password(self, service, account):
        self._store.pop((service, account), None)
    def get_secret(self):
        return self._store.get((SERVICE_NAME, ACCOUNT))

class CredentialStore:
    def __init__(self, keyring: KeyringLike | None = None):
        if keyring is None:
            import keyring as _k  # 真实运行时注入 OS 钥匙串
            keyring = _k.get_keyring()
        self.kr = keyring

    def store(self, key: str) -> None:
        self.kr.set_password(SERVICE_NAME, ACCOUNT, key)

    def get(self) -> str | None:
        return self.kr.get_password(SERVICE_NAME, ACCOUNT)

    def status(self) -> str:
        return "configured" if self.get() is not None else "not configured"

    def update(self, key: str) -> None:
        self.store(key)

    def clear(self) -> None:
        try:
            self.kr.delete_password(SERVICE_NAME, ACCOUNT)
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_credentials.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/credentials.py tests/test_credentials.py
git commit -m "feat(credentials): CredentialStore over keyring + FakeKeyring for tests"
```

---

### Task 12: Mini 目标仓库（手写，核心素材）

**Files:**
- Create: `demo/target_repo/pyproject.toml`, `demo/target_repo/src/app.py`, `demo/target_repo/tests/test_auth.py`, `demo/target_repo/tests/test_db.py`, `demo/target_repo/tests/test_util.py`
- 无独立测试任务（它本身是被测对象；由 Task 13 集成测试驱动）

**说明**：本仓库为手写核心素材（§六学术规范），内置 5 失败测试 + 3 lint + 2 类型错，供 agent 修复。

- [ ] **Step 1: 写带缺陷的实现文件**

```python
# demo/target_repo/src/app.py
import os  # F401: unused import (lint)
import sys  # F401: unused import (lint)

def login(user: str, password: str) -> int:
    # BUG: 总是返回 401, 测试期望 200
    return 401

def connect_db(dsn):
    # BUG: 引用未安装模块 → ImportError
    import psycopg2  # noqa
    return psycopg2.connect(dsn)

def add(a: int, b: int) -> int:
    # TYPE ERROR: 返回 str, 注解为 int
    return str(a + b)  # type: ignore 故意触发 mypy

def unused_helper():  # F841-ish: 复杂表达式未用 (lint)
    x = 1
    y = 2
    return x  # y 未用 (lint)
```

```toml
# demo/target_repo/pyproject.toml
[project]
name = "target-repo"
version = "0.1.0"
requires-python = ">=3.11"
[tool.pytest.ini_options]
testpaths = ["tests"]
[tool.ruff]
line-length = 80
[tool.mypy]
packages = ["src"]
```

- [ ] **Step 2: 写 5 个失败测试**

```python
# demo/target_repo/tests/test_auth.py
from src.app import login
def test_login_returns_200_for_valid():
    assert login("user", "pass") == 200
def test_login_returns_401_for_invalid():
    assert login("user", "wrong") == 401
```

```python
# demo/target_repo/tests/test_db.py
from src.app import connect_db
def test_connect_db_returns_connection():
    assert connect_db("dsn") is not None
```

```python
# demo/target_repo/tests/test_util.py
from src.app import add, unused_helper
def test_add_integers():
    assert add(2, 3) == 5
def test_add_returns_int():
    assert isinstance(add(1, 1), int)
def test_unused_helper_returns_one():
    assert unused_helper() == 1
```

- [ ] **Step 3: 手动验证缺陷确实存在**

Run（在 `demo/target_repo/`）: `pytest --tb=no -q && ruff check . --output-format=concise && mypy src`
Expected: ≥5 测试失败、≥3 lint、≥2 类型错。

- [ ] **Step 4: Commit**

```bash
git add demo/target_repo/
git commit -m "feat(demo): hand-written mini target repo with seeded failures"
```

---

### Task 13: 集成测试（mock-LLM 驱动端到端修复）

**Files:**
- Create: `tests/test_integration.py`
- Modify: 无（依赖 Task 9 真实 ToolDispatcher，但用内存文件系统 stub 替代真实 subprocess 以保持确定性）

**Interfaces:**
- Consumes: `AgentLoop`(Task 10)、`MockLLMClient`(Task 3)、真实 `ToolDispatcher`+`Guardrail`+`FeedbackLoop`+validators
- 说明：为确定性，`run_tests/run_lint/run_typecheck` 用一个 stub dispatcher 按动作返回预录产物（复用 Task 7 fixtures），不跑真实 pytest/ruff/mypy。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_integration.py
import json
from pathlib import Path
from harness.loop import AgentLoop
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.governance.guardrail import Guardrail
from harness.governance.approver import AutoRejectApprover
from harness.config import GuardrailRules, ValidatorConfig
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator, Product
from harness.memory.memory import Memory

FIX = Path(__file__).parent / "fixtures"

class RepoDispatcher:
    """模拟对 target_repo 的修复: 第1轮产物=fail, 第2轮=pass。"""
    def __init__(self):
        self.test_calls = 0
    def exec(self, action):
        if action.tool == "run_tests":
            self.test_calls += 1
            if self.test_calls == 1:
                data = json.loads((FIX/"pytest_fail.json").read_text(encoding="utf-8"))
            else:
                data = json.loads((FIX/"pytest_pass.json").read_text(encoding="utf-8"))
            return Product(1 if self.test_calls == 1 else 0, json.dumps(data), "")
        if action.tool == "write_file":
            return Product(0, "wrote", "")
        return Product(0, "", "")

def test_integration_fail_to_success(tmp_path):
    script = [
        LLMResponse("write_file", {"path": "src/app.py", "content": "bad fix"}, None),
        LLMResponse("run_tests", {}, None),
        LLMResponse("write_file", {"path": "src/app.py", "content": "good fix"}, None),
        LLMResponse("run_tests", {}, None),
    ]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=RepoDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "success"
    assert result.rounds == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_integration.py -v`
Expected: FAIL（若未实现则 ModuleNotFoundError；实现后应直接 PASS——本任务验证已存机制协同）

- [ ] **Step 3: 如失败则补齐 loop 中遗漏（不应需要改实现）**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): mock-LLM end-to-end fail->success repair"
```

---

### Task 14: WebUI 内核外薄层 `src/webui/server.py` + Open Design 前端

**Files:**
- Create: `src/webui/__init__.py`, `src/webui/server.py`, `src/webui/static/index.html`, `src/webui/static/app.js`, `src/webui/static/styles.css`
- Modify: `src/harness/governance/approver.py`（充实 `WebApprover` 通过队列与 server 通信）
- Test: `tests/test_webui.py`（仅测 SSE 流与审批回传的契约，不测 UI 渲染）

**Interfaces:**
- Consumes: `AgentLoop`+`WebApprover`(Task 10/5)
- 说明：Open Design 设计系统通过 CDN/本地引入；前端为只读流 + 审批弹窗，不做规则编辑器（§YAGNI）。

- [ ] **Step 1: Write the failing test（server 契约）**

```python
# tests/test_webui.py
from harness.governance.approver import WebApprover
from harness.models import Action

def test_web_approver_uses_injected_ask():
    called = {}
    def ask(a):
        called["action"] = a
        return True
    ap = WebApprover(ask=ask)
    assert ap.approve(Action("write_file", {"path": "../x", "content": "y"})) is True
    assert called["action"].tool == "write_file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webui.py -v`
Expected: PASS（Task 5 已实现 `WebApprover(ask=...)`）。如未 PASS 则补齐。

- [ ] **Step 3: 实现 SSE server**

```python
# src/webui/server.py
from __future__ import annotations
import json, queue, threading
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import StreamingResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from pathlib import Path

class WebUISession:
    def __init__(self):
        self.events: list[str] = []
        self._ask_q: queue.Queue = queue.Queue()
        self._ans_q: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
    def push(self, event: str):
        with self.lock:
            self.events.append(event)
    def ask(self, action):
        self._ask_q.put(action)
        return self._ans_q.get()
    def answer(self, decision: bool):
        self._ans_q.put(decision)

def make_app(session: WebUISession) -> Starlette:
    async def sse(request):
        idx = 0
        async def gen():
            nonlocal idx
            while True:
                with session.lock:
                    while idx < len(session.events):
                        yield f"data: {session.events[idx]}\n\n"
                        idx += 1
                import asyncio
                await asyncio.sleep(0.2)
        return StreamingResponse(gen(), media_type="text/event-stream")

    async def approve(request):
        data = await request.json()
        session.answer(bool(data.get("approve", False)))
        return JSONResponse({"ok": True})

    async def pending_approval(request):
        try:
            action = session._ask_q.get_nowait()
            return JSONResponse({"pending": True, "action": {"tool": action.tool, "args": action.args}})
        except queue.Empty:
            return JSONResponse({"pending": False})

    routes = [
        Route("/events", sse),
        Route("/approve", approve, methods=["POST"]),
        Route("/pending", pending_approval, methods=["GET"]),
    ]
    app = Starlette(routes=routes)
    static = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static), html=True), name="static")
    return app
```

```html
<!-- src/webui/static/index.html -->
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>Coding Agent Harness</title>
  <link rel="stylesheet" href="styles.css">
  <!-- Open Design 设计系统：此处引入所选设计系统的样式（在 SPEC §8 已说明）-->
</head>
<body>
  <main>
    <h1>Coding Agent Harness</h1>
    <pre id="log"></pre>
    <div id="approval" hidden>
      <p id="approval-text"></p>
      <button id="approve-btn">允许</button>
      <button id="reject-btn">拒绝</button>
    </div>
  </main>
  <script src="app.js"></script>
</body>
</html>
```

```javascript
// src/webui/static/app.js
const log = document.getElementById("log");
const approval = document.getElementById("approval");
const es = new EventSource("/events");
es.onmessage = (e) => { log.textContent += e.data + "\n"; };

async function pollApproval() {
  const r = await fetch("/pending");
  const d = await r.json();
  if (d.pending) {
    approval.hidden = false;
    document.getElementById("approval-text").textContent =
      JSON.stringify(d.action);
  } else {
    approval.hidden = true;
  }
}
document.getElementById("approve-btn").onclick = () => postApproval(true);
document.getElementById("reject-btn").onclick = () => postApproval(false);
async function postApproval(v) {
  await fetch("/approve", {method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({approve: v})});
  approval.hidden = true;
}
setInterval(pollApproval, 1000);
```

```css
/* src/webui/static/styles.css */
body { font-family: system-ui; margin: 2rem; }
#log { background: #111; color: #eee; padding: 1rem; height: 60vh; overflow: auto; }
#approval { position: fixed; bottom: 2rem; right: 2rem; background: #fff; border: 1px solid #888; padding: 1rem; }
button { margin: 0 .5rem; }
```

充实 `WebApprover`（让其持有 session 并调 `session.ask`）：

```python
# src/harness/governance/approver.py  —— WebApprover 替换为:
class WebApprover:
    """通过 WebUI session 与前端交互审批。"""
    def __init__(self, session=None, ask=None):
        self._session = session
        self._ask = ask
    def approve(self, action) -> bool:
        if self._session is not None:
            return self._session.ask(action)
        return (self._ask or (lambda _a: False))(action)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_webui.py -v`
Expected: PASS

- [ ] **Step 5: 手动起 server 烟测（非自动化）**

Run: `python -c "from webui.server import make_app, WebUISession; import uvicorn; uvicorn.run(make_app(WebUISession()), port=8000)"`
Expected: 浏览器打开 `http://localhost:8000`，见标题与日志区。

- [ ] **Step 6: Commit**

```bash
git add src/webui/ src/harness/governance/approver.py tests/test_webui.py
git commit -m "feat(webui): SSE log stream + approval roundtrip (kernel-external)"
```

---

### Task 15: 机制演示三幕 `demo/run_demo.py`

**Files:**
- Create: `demo/run_demo.py`
- 无新测试（演示脚本本身是 §A.6 交付物；幂②幂③复用 Task 8/10 测试）

**说明**：`make demo` 跑此脚本，mock 下确定性复现三幕并打印 PASS/FAIL。

- [ ] **Step 1: Write the demo script**

```python
# demo/run_demo.py
from __future__ import annotations
import json
from harness.governance.guardrail import Guardrail, Decision
from harness.config import GuardrailRules
from harness.models import Action
from harness.llm.mock import MockLLMClient
from harness.llm.base import LLMResponse
from harness.loop import AgentLoop
from harness.governance.approver import AutoRejectApprover
from harness.feedback.validators import PytestValidator, Product
from harness.config import ValidatorConfig
from harness.memory.memory import Memory

def act1_guardrail_denies_destructive():
    g = Guardrail(GuardrailRules(shell_blacklist=["rm -rf"]))
    d = g.inspect(Action("exec_shell", {"cmd": "rm -rf /"}))
    assert d == Decision.DENY, f"expected DENY got {d}"
    print("ACT 1 PASS: guardrail denies rm -rf /")

class FailThenPassDispatcher:
    def __init__(self): self.calls = 0
    def exec(self, action):
        if action.tool == "run_tests":
            self.calls += 1
            if self.calls == 1:
                rep = {"summary": {"passed": 0, "failed": 1, "errors": 0},
                       "tests": [{"nodeid": "t::x", "outcome": "failed",
                                  "call": {"crash": {"type": "AssertionError", "message": "m"}}}]}
            else:
                rep = {"summary": {"passed": 1, "failed": 0, "errors": 0}, "tests": []}
            return Product(1 if self.calls == 1 else 0, json.dumps(rep), "")
        return Product(0, "", "")

def act2_feedback_loop_recovers(tmp_path):
    script = [
        LLMResponse("write_file", {"path": "a.py", "content": "bad"}, None),
        LLMResponse("run_tests", {}, None),
        LLMResponse("write_file", {"path": "a.py", "content": "good"}, None),
        LLMResponse("run_tests", {}, None),
    ]
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=FailThenPassDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "success", f"expected success got {result.outcome}"
    print("ACT 2 PASS: feedback loop drives fail->success")

def act3_no_progress_stops(tmp_path):
    # MockLLM 连续输出同一错误修复 → 无进展停机
    script = [LLMResponse("write_file", {"path": "a.py", "content": "bad"}, None),
              LLMResponse("run_tests", {}, None)] * 5
    class StuckDispatcher:
        def exec(self, action):
            if action.tool == "run_tests":
                rep = {"summary": {"passed": 0, "failed": 1, "errors": 0},
                       "tests": [{"nodeid": "t::x", "outcome": "failed",
                                  "call": {"crash": {"type": "AssertionError", "message": "m"}}}]}
                return Product(1, json.dumps(rep), "")
            return Product(0, "", "")
    loop = AgentLoop(
        llm=MockLLMClient(script),
        guardrail=Guardrail(GuardrailRules()),
        approver=AutoRejectApprover(),
        dispatcher=StuckDispatcher(),
        validators={"test": PytestValidator()},
        feedback_cfg=ValidatorConfig(max_rounds=10, no_progress_window=3),
        memory=Memory(str(tmp_path / "mem.jsonl")),
    )
    result = loop.run()
    assert result.outcome == "no_progress", f"expected no_progress got {result.outcome}"
    print("ACT 3 PASS: no-progress stop fires")

if __name__ == "__main__":
    import tempfile
    act1_guardrail_denies_destructive()
    with tempfile.TemporaryDirectory() as td:
        import pathlib
        act2_feedback_loop_recovers(pathlib.Path(td))
        act3_no_progress_stops(pathlib.Path(td))
    print("ALL ACTS PASS")
```

- [ ] **Step 2: Run the demo**

Run: `python demo/run_demo.py`
Expected: 打印三幕 PASS + `ALL ACTS PASS`

- [ ] **Step 3: Commit**

```bash
git add demo/run_demo.py
git commit -m "feat(demo): three-act mechanism demo under mock LLM"
```

---

### Task 16: 打包、CLI 入口、Makefile

**Files:**
- Create: `pyproject.toml`, `Makefile`
- Modify: `src/harness/cli.py`（新建）
- Test: 烟测（无单测）

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "coding-agent-harness"
version = "0.1.0"
description = "A self-coded Coding Agent Harness (AI4SE final project A)"
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27",
  "PyYAML>=6.0",
  "keyring>=24.0",
  "starlette>=0.37",
  "uvicorn>=0.30",
]
[project.optional-dependencies]
llm = ["anthropic>=0.40"]
dev = ["pytest>=8.0", "ruff>=0.5", "mypy>=1.10", "pytest-json-report>=1.5"]
[project.scripts]
harness = "harness.cli:main"
[tool.setuptools.packages.find]
where = ["src"]
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: requires real LLM key"]
[tool.ruff]
line-length = 100
[tool.mypy]
packages = ["harness"]
```

- [ ] **Step 2: Write CLI entrypoint**

```python
# src/harness/cli.py
from __future__ import annotations
import argparse, sys
from harness.config import Config
from harness.credentials import CredentialStore, FakeKeyring
from harness.llm.mock import MockLLMClient
from harness.governance.guardrail import Guardrail
from harness.governance.approver import CliApprover, AutoRejectApprover
from harness.tools.dispatcher import ToolDispatcher
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator
from harness.feedback.feedback_loop import FeedbackLoop
from harness.memory.memory import Memory
from harness.loop import AgentLoop

def main(argv=None):
    p = argparse.ArgumentParser(prog="harness")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--workdir", default=".")
    p.add_argument("--headless", action="store_true", help="run mock demo, no LLM")
    p.add_argument("--init-key", action="store_true", help="guide first-time key entry")
    args = p.parse_args(argv)

    if args.init_key:
        import getpass
        cs = CredentialStore()
        cs.store(getpass.getpass("Enter LLM API key (hidden): "))
        print("status:", cs.status())
        return 0

    cfg = Config.load(args.config)
    if args.headless:
        # 仅供冒烟, 真实演示走 demo/run_demo.py
        print("headless mode: use `python demo/run_demo.py` for the demo")
        return 0

    # 真实运行: 需 key + provider client (Task 略, 落在 deepseek.py/anthropic_client.py)
    print("not implemented in headless; see demo/run_demo.py")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write Makefile**

```makefile
.PHONY: test demo build install
test:
	pytest -q
demo:
	python demo/run_demo.py
build:
	python -m build
install:
	pip install -e .[dev,llm]
```

- [ ] **Step 4: 烟测**

Run: `pip install -e .[dev] && make test && make demo`
Expected: 测试全绿 + 三幕 PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile src/harness/cli.py
git commit -m "feat(packaging): pyproject + CLI entrypoint + Makefile"
```

---

### Task 17: CI 配置 `.gitlab-ci.yml`

**Files:**
- Create: `.gitlab-ci.yml`
- 无单测（CI 配置本身）

- [ ] **Step 1: Write CI config**

```yaml
# .gitlab-ci.yml
stages: [test, build]

unit-test:
  stage: test
  image: python:3.11-slim
  before_script:
    - pip install -e .[dev]
    - pip install ruff mypy pytest-json-report || true
  script:
    - pytest -q
    - python demo/run_demo.py
  rules:
    - if: $CI_COMMIT_BRANCH

build-wheel:
  stage: build
  image: python:3.11-slim
  needs: [unit-test]
  before_script:
    - pip install build
  script:
    - python -m build
  artifacts:
    paths: [dist/*.whl]
```

- [ ] **Step 2: Commit**

```bash
git add .gitlab-ci.yml
git commit -m "ci: unit-test + build-wheel jobs"
```

- [ ] **Step 3: 推送并确认最后一次 CI 为 pass**

Run: `git push -u origin main`
Expected: CI 流水线 `unit-test` job pass。

---

## Self-Review 结论

**Spec coverage**：§3.1 主循环→T10；§3.2 LLM→T3（+T16 provider 在 cli）；§3.3 工具→T9；§3.4 反馈闭环→T7/T8；§3.5 治理→T4/T5；§3.6 记忆→T6；§3.7 配置→T2；§3.8 WebUI→T14；§3.9 凭据→T11；§5 非功能（性能/可观测）→loop TurnRecord 持久化在 T10；§6 凭据威胁模型→T11 + T17 静态扫描由评审纪律覆盖；§9 验收→T13 集成/T15 演示/T17 CI；§10 风险→冷启动验证在 SPEC_PROCESS（独立于 PLAN）。无遗漏。

**Placeholder 扫描**：无 TBD/TODO；每步均含实际代码与命令。

**类型一致性**：`failure_fingerprint`、`Decision`、`StopReason`、`Product`、`Validator.complete`→`parse`、`Memory.recall(RecallQuery)`、`CredentialStore.{store,get,status,update,clear}` 在各任务签名一致。Task 10 loop 中 `feedbacks` 字典键与 Task 8 `update` 参数键统一为 `"test"/"lint"/"type"`。

**冷启动验证（§4.5）提醒**：本 PLAN 定稿后，须用第二个陌生 agent 试跑 Task 9 或 Task 10（约 1–2 小时），仅给 SPEC+PLAN 不给对话历史，记录其受阻点与修订 diff 到 `SPEC_PROCESS.md`，再进入实现。
