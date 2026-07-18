# SPEC.md · Coding Agent Harness

> *Spec-Driven, Subagent-Built, Human-Owned.*
> 本 SPEC 由 `superpowers:brainstorming` 技能协同产出，遵循《AI4SE 期末项目 · 通用要求》与《A · Coding Agent Harness》两份要求文件。在 SPEC 与 PLAN 通过冷启动验证前，禁止编写任何实现代码。

---

## 1. 问题陈述

当 LLM 能完成大部分编码思考时，工程师的真正价值落在 **harness 这层工程**（治理、反馈、上下文、安全、分发）。本项目交付一台**自编码的 Coding Agent Harness**：

- 给定一个有失败测试 / lint / 类型错误的小型 Python 仓库，它能自主读代码、改代码、跑校验；
- 据**客观结构化反馈**多轮自我修正，直到通过或满足停机条件；
- 在危险动作执行前停下，等待人工审批（HITL）；
- 跨会话记住项目约定与失败教训，按需提供给 LLM 而非全量载入。

**核心等式**：`Agent = LLM + Harness`。LLM 只负责"决定下一步做什么"这一行任务决策；主循环、工具分发、治理护栏、反馈闭环、记忆、配置——全部由本项目自己的代码实现，不寄生于任何现成 agent 编排框架的高层循环。

**目标用户**：想第一手理解"用 harness 去造 harness"的工程师 / AI4SE 学习者。

**价值**：把 `Agent = LLM + Harness` 这个等式里"Harness"那一层亲手编码，并对这套方法论形成批判性理解。

---

## 2. 用户故事（遵循 INVEST）

1. **(修复)** 作为开发者，我给定一个带失败测试的小仓库，启动 agent，使它在不需我介入的情况下让测试转绿，以便我验证 harness 的反馈闭环确实能驱动 agent 自我修正。
2. **(治理)** 作为开发者，当 agent 试图执行 `rm -rf`、`git push` 或改写 CI 配置时，harness 拦截该动作并请求我审批，以便我保留对危险操作的掌控。
3. **(反馈分类)** 作为开发者，我希望 agent 收到的失败反馈是结构化的（按 test/lint/type 分类、按失败 kind 标注、带定位），而非原始报错全文，以便 agent 的修正策略可被单测验证、且 context 占用更小。
4. **(停机)** 作为开发者，我希望 agent 在"连续 N 轮无进展"或"达最大轮次"时自动停机并报告原因，以便它不会在死循环里烧 token。
5. **(记忆)** 作为开发者，我希望 agent 跨会话记住"本项目用 pytest+ruff+py3.11"及"上次误改 conftest 导致全崩"这类教训，以便它不在同一类问题上反复栽跟头。
6. **(WebUI)** 作为外部评审者，我希望通过一个浏览器界面观看 agent 的每一步循环、并对危险动作弹窗审批，以便我在一台全新机器上从零运行并验证它（满足通用要求 §5.9）。
7. **(凭据)** 作为用户，我希望首次运行时被引导隐藏录入 LLM key、查看时只见状态不见明文、可随时更新或清除，以便 key 绝不落明文。

---

## 3. 功能规约（按模块）

### 3.1 Agent 主循环 `AgentLoop`
- **输入**：目标仓库路径、初始任务描述、Config、LLMClient、Approver、Memory
- **行为**：`while not stopped: 组装 context → llm.complete(tools) → 解析 Action → guardrail.inspect → (必要时)approver.approve → dispatch.exec → validator.parse → feedback_loop.update → 回灌 → 判停机`
- **输出**：`RunResult { outcome: success|no_progress|max_rounds, rounds, turn_records }`
- **边界**：上下文超 token 上限时按轮次裁剪历史；解析失败的动作回灌"无法解析"而非崩溃
- **错误处理**：LLM 调用异常重试 3 次后停机；工具执行异常被 Guardrail/Dispatcher 包裹回灌

### 3.2 LLM 抽象层 `LLMClient`
- **接口**：`complete(messages, tools_schema) -> {action_tool_call | text | parse_error}`
- **实现**：`DeepSeekClient`（默认）、`AnthropicClient`（可选）、`MockLLMClient`（单测注入，按脚本回放动作）
- **边界**：对 function-calling 不遵从做 robust 解析 + 失败重试；单测只用 Mock

### 3.3 工具分发 `ToolDispatcher`
- **工具集**：`read_file / write_file / exec_shell / run_tests / run_lint / run_typecheck`
- **行为**：`exec(Action) -> Product（stdout/stderr/exitcode/文件变更）`
- **边界**：`write_file` 路径校验不得逃逸工作目录；`exec_shell` 产物先交 Validator 再回灌

### 3.4 反馈闭环 `FeedbackLoop`（★ 重点维度）
- **校验器**：`PytestValidator`（`pytest --json-report`）/ `RuffValidator`（`ruff --output-format=json`）/ `MypyValidator`（mypy JSON）
- **解析**：产物 → `Feedback { source, verdict, failures: [Failure{kind, location, message}] }`
- **失败分类**：封闭枚举 `FailureKind`（见 §4）
- **停机判断**：success（全 pass）/ no_progress（连续 3 轮失败指纹无变化）/ max_rounds（10）
- **回灌**：结构化摘要注入 context，非原始报错全文
- **单测**：MockLLM 编排 → 断言回灌结构、三种停机

### 3.5 治理护栏 `Guardrail` + `Approver`
- **判定**：`inspect(Action) -> Allow | Deny | NeedApproval`
- **规则集**（声明式 config）：
  - 越界文件（绝对路径 / `../..` 逃逸）→ NeedApproval
  - CI/凭据文件（`.gitlab-ci.yml`、`.github/`、`.env`）→ Deny
  - 网络：白名单放行 `pip install`/`npm install`/`mvn verify`，黑名单拦 `curl`/`wget`/`iptables`
  - git：`commit` 放行、`push` Deny
  - 破坏 shell：黑名单正则 `rm -rf`/`sudo`/`chmod 777`/`mkfs`/`DROP`/`TRUNCATE`
- **Approver 实现**：`CliApprover`（终端 y/N）/ `WebApprover`（WebUI 弹窗）/ `AutoRejectApprover`（单测 DI 注入）
- **单测**：构造动作断言判定；AutoReject 注入测 NeedApproval→Deny 路径

### 3.6 记忆 `Memory`（自实现）
- **存储**：`.agent_memory/` 下 JSON Lines，条目含 `{id, tags, content, created_at}`
- **检索**：`recall(RecallQuery) -> [MemoryEntry]`，按 tag 交集 + 可选 source 过滤
- **按需载入**：首轮载入"项目约定"；后续轮据当前失败信号 tag 检索；不全量载入
- **单测**：store → recall 断言包含

### 3.7 配置 `Config`
- **形态**：声明式 `config.yaml`（guardrail 规则、validator 开关与阈值、LLM provider、记忆库路径）
- **行为**：`Config.load(path) -> 强类型对象`；规则是数据，识别是代码（符合 §A.4-B）
- **单测**：加载测试 config，断言 guardrail 据此对构造动作的判定

### 3.8 WebUI（内核外薄层）
- **职责**：SSE 流式推送每轮 `TurnRecord`；POST 回传审批决策；用 Open Design 设计系统
- **边界**：不参与 mock 单测；仅通过 `Approver` 接口与内核交互
- **豁免**：纯前端薄层，不属 harness 内核机制（§A.4-C 判据对内核成立）

### 3.9 凭据管理 `CredentialStore`
- **接口**：`store/get/status/update/clear`
- **主**：OS 钥匙串（`keyring` → Windows Credential Manager / macOS Keychain / Linux Secret Service）
- **次**：`.env` 加载（**标注明文风险**：文件明文、进程环境可见）
- **首次录入**：`getpass` 隐藏输入；查看只显 `configured`/`not configured`，不回显
- **单测**：in-memory fake keyring 注入，测四路径

---

## 4. 领域与机制设计（§A.5 必需节）

### coding 领域四类机制如何编码

| 机制 | coding 形态 | 编码为（确定性可单测） |
|---|---|---|
| 动作/工具 | 读/写文件、执行 shell、跑测试/lint/type | `ToolDispatcher` + 工具集；产物回灌 Validator |
| 客观反馈信号★重点 | pytest/ruff/mypy 结构化产物 → pass/fail + 定位 | `Validator` → `Feedback`（封闭枚举）→ 回灌；`FeedbackLoop` 编排 + 指纹比对 + 判停机 |
| 危险动作 | 越界文件、改 CI/凭据、curl/wget、git push、rm -rf/sudo/mkfs/DROP | `Guardrail`（声明式规则 + 黑/白名单 + 正则）→ `Allow/Deny/NeedApproval`；`Approver` 三实现 |
| 记忆 | 项目约定、历史失败教训 | `Memory`（JSON Lines + tag 检索，自实现 store/recall） |

### 失败分类法（封闭枚举）

```python
class Source(Enum):     TEST = "test";   LINT = "lint";   TYPE = "type"
class FailureKind(Enum):
    ASSERTION_ERROR      # 测试断言失败
    COLLECTION_ERROR     # pytest 收集阶段失败
    IMPORT_ERROR         # ImportError
    TIMEOUT              # 命令/测试超时
    LINT_VIOLATION       # ruff 规则违反
    TYPE_VIOLATION       # mypy 类型错误
    UNKNOWN              # 兜底, 不进"已分类可修正"路径
```

失败指纹 = `frozenset({(source, kind, location)})`，不含 `message`（避免文本变化误判为有进展）。

### 为什么反馈闭环是重点

coding 修复任务里 agent 每一步都依赖"修改是否正确"的客观信号；反馈闭环把"解析产物 → 客观判定 → 结构化失败 → 回灌 → 停机"串成一条**全代码、无 LLM 介入判定**的链，是 §A.4 (A)(B)(C) 三条判据最集中的落点。治理 / 记忆 / 工具 / 配置为支撑性最低实现，避免六维都浅。

### "移除 LLM 后还剩多少可独立验证的工程"自检

移除真实 LLM、注入 `MockLLMClient` + `AutoRejectApprover` 后仍可单测：主循环分发、护栏拦截、校验器解析、失败分类、无进展停机、记忆读写、keyring 抽象。这些即交付的 harness 机制。WebUI / 真实 LLM / 提示词文件属"内容物"或"内核外薄层"，不计入机制工作量。

---

## 5. 非功能性需求

- **性能**：单轮 loop 本身开销 < 1s（不含 LLM 调用）；校验器解析 < 500ms
- **安全**：见 §6 威胁模型；harness 仅在工作目录内写文件；shell 受 guardrail 围栏
- **可用性**：WebUI 用 Open Design；CLI `--headless` 跑 mock 演示；`make test` / `make demo` 一键
- **可观测性**：每轮 `TurnRecord` 持久化到 `.agent_runs/` JSONL；WebUI 实时流式；停机输出结构化诊断（原因 + 最后失败指纹）

---

## 6. 系统架构与凭据威胁模型

### 架构（单进程，三态）

```
CLI 开发态 (CliApprover) ──┐
WebUI 部署态 (WebApprover) ─┼─> Harness 内核 (自编码, mock 可单测)
Headless 测试态 (AutoReject) ─┘
   ├─ AgentLoop ─ ToolDispatcher ─ Validator 套件
   ├─ FeedbackLoop★(重点) ─ Guardrail ─ Approver(接口)
   ├─ Memory(tag检索) ─ Config(声明式)
   └─ LLMClient 接口: DeepSeek | Anthropic | Mock
```

WebUI 为内核外薄层（SSE + POST 审批），不参与 mock 单测，保证 §A.4-C 判据成立。

### 外部依赖
- **LLM 供应商**：DeepSeek（默认）、Anthropic（可选）；单测用 Mock，不依赖网络
- **校验工具链**：pytest、ruff、mypy（目标仓库与 harness 同为 Python）
- **凭据库**：`keyring`（OS 钥匙串）
- **前端**：Open Design 设计系统

### 凭据威胁模型与对策

| 威胁 | 对策 |
|---|---|
| key 硬编码源码 | CI 静态扫描（API key 模式 grep）+ 评审纪律 |
| key 进 git 历史 | `.gitignore` 排除 `.env`；pre-commit 扫描钩子 |
| key 写日志 / 终端 history | 日志对 key 字段 redact；不打印 Authorization 头 |
| key 明文落盘 | **主**：OS 钥匙串；**次**：`.env` 加载并**标注明文风险**（文件明文、进程环境可见、`/proc` 可读） |
| 首次录入泄漏 | `getpass` 隐藏输入 |
| 查看/更新/清除 | 查看只显状态不回显；更新即覆盖；清除即删钥匙串条目 |

### 分发
- **形态**：PyPI 包 + 原生运行；`pip install <pkg>` 即装
- **CI**：`build` job 构建 wheel；可选 Docker 镜像作演示
- **README 须写清**：获取命令、运行命令、key 在目标机的安全配置（钥匙串）、已知限制（Win/macOS/Linux、Python ≥ 3.11、需 pytest/ruff/mypy）
- **云部署（§4.11）**：WebUI 部署到 Render/Railway 等免费额度，提供公网 URL；README 说明部署架构与 CI/CD

---

## 7. 数据模型

```python
@dataclass
class Action:           tool: str;  args: dict
@dataclass
class Feedback:         source: Source;  verdict: Verdict;  failures: list[Failure]
@dataclass
class Failure:          kind: FailureKind;  location: str;  message: str
@dataclass
class TurnRecord:       round: int;  action: Action;  feedback: Feedback|None
                        guardrail_decision: str;  failure_fingerprint: frozenset|None
@dataclass
class MemoryEntry:      id: str;  tags: list[str];  content: str;  created_at: str
@dataclass
class RunResult:        outcome: Literal["success","no_progress","max_rounds"]
                        rounds: int;  turn_records: list[TurnRecord]
```

---

## 8. 技术选型与理由

| 选型 | 理由 |
|---|---|
| **Python**（harness 与目标仓库同语言） | 生态熟、LLM SDK 全、keyring 成熟；pytest/ruff/mypy 产物解析最干净；单人期末摩擦最小 |
| **DeepSeek**（默认 LLM） | 国内网络顺、成本低；工具调用偶不稳由 LLMClient 层 robust 解析缓解；单测不依赖 |
| **Anthropic**（可选） | 工具调用最稳，作 fallback；接口统一 |
| **PyPI 分发 + OS keyring** | 与 Windows 环境、CLI/Web HITL、凭据安全天然契合，凭据做到"最好形态" |
| **SSE（非 WS）** | 单向流式足够、实现简 |
| **Open Design**（前端） | 通用要求 §3.4 推荐；满足 WebUI 要求 |
| **放弃 OS 沙箱，用 guardrail 规则围栏** | Windows 沙箱方案少且依赖外部能力；规则围栏全自编码，符合 §A.4 红线 |

---

## 9. 验收标准

1. `make test` 全绿，含 mock-LLM 驱动的机制单测（护栏 / 校验器 / 反馈闭环 / 记忆 / keyring），无网络无真实 LLM。
2. `make demo` 确定性复现 §A.6 三幕：①护栏拦 `rm -rf`；②注入失败→反馈回灌→MockLLM 改动作→success；③无进展停机。
3. 集成测试：mini 目标仓库（5 失败测试 + 3 lint + 2 类型错）从 fail 走到 success。
4. 真实 LLM 冒烟（`@live` 标记，CI skip）：用真实 key 跑通至少一次完整修复。
5. WebUI 公网可访问，能流式观看 loop 步骤并完成一次审批（§5.9）。
6. 凭据：首次隐藏录入、查看不回显、可更新/清除；CI 静态扫描无 key 泄漏。
7. CI（`.gitlab-ci.yml`）含 `unit-test` job，最后一次 pass。
8. 仓库无真实凭据；commit/PR 历史规范；PLAN 持续更新。

---

## 10. 风险与未决问题

1. **国产 LLM 工具调用稳定性**：DeepSeek 偶发不遵从 function-calling → LLMClient robust 解析 + 重试；单测用 Mock 规避。
2. **mini 目标仓库**：~200 行 Python 小项目（认证/数据层），内置 5 失败测试 + 3 lint + 2 类型错。**核心素材手写**（§六学术规范，核心算法/素材手写更稳）。
3. **无进展检测误判**：极端情况仍可能 → 已通过"指纹不含 message"缓解，列为已知限制。
4. **Windows 沙箱缺失**：用 guardrail 规则围栏替代 OS 沙箱，为已知设计取舍。
5. **WebUI 工作量**：前端 + SSE + 部署是计划里最大非机制块，须在 PLAN 拆细、严控范围（只读流 + 审批弹窗，不做规则编辑器）。
6. **冷启动验证**（§4.5）：SPEC + PLAN 完成后，用第二个陌生 agent 试跑 1–2 个 task，暴露 spec 缺陷并修订，记录到 `SPEC_PROCESS.md`。

---

## 附录 · 机制演示三幕映射（§A.6）

| 幕 | 复现行为 | 机制 | 判定 |
|---|---|---|---|
| ① | `guardrail(ShellAction("rm -rf /")) == Deny`；`AutoReject` 注入测 NeedApproval→Deny | Guardrail + Approver | 确定性 pass |
| ② | MockLLM 先输出错误修复使 pytest fail → FeedbackLoop 回灌结构化反馈 → MockLLM 下一轮输出正确修复 → success | FeedbackLoop | 确定性 pass |
| ③ | MockLLM 连续输出相同错误修复 → 第 3 轮后 FeedbackLoop 返回 `stop(no_progress)` | FeedbackLoop 无进展停机 | 确定性 pass |
