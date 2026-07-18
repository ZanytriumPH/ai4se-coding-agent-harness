# AGENT_LOG.md · Coding Agent Harness (AI4SE 期末项目 A)

> 过程日志：记录开发过程中触发的 Superpowers 技能、子代理提交、人工干预与裁决。对应通用要求 §4.4。

---

## 0. 总览

- **项目**：自编码 Coding Agent Harness（内核自实现主循环 + Mock-LLM 抽象；机制以代码而非 prompt 实现；移除真实 LLM 后机制仍可确定性单测，§A.4-C）。
- **技术栈**：Python；DeepSeek 默认 / Anthropic 可选；PyPI + OS 钥匙串分发；WebUI(Open Design) 为主交互面（内核外薄层）。
- **重点维度（§A.4-D 深一处）**：反馈闭环（FailureKind 封闭枚举 + 失败指纹不含 message + NO_PROGRESS/MAX_ROUNDS 停机）。
- **开发纪律**：Superpowers brainstorming → writing-plans → §4.5 冷启动验证 → subagent-driven-development（每 task 新子代理 + 任务评审 + 整支终评）。TDD 红-绿-重构，频繁提交。
- **PR 策略**：合并为 5 个 PR（基座 / 机制层 / 集成 / WebUI+演示 / 打包+CI），每 PR 一个工作树分支。

---

## 1. 触发的技能（时序）

| # | 技能 | 产物 | 备注 |
|---|---|---|---|
| 1 | `superpowers:brainstorming` | `SPEC.md` | 苏格拉底式一次一问，10 节 + 机制演示三幕映射。过程见 `SPEC_PROCESS.md`。 |
| 2 | `superpowers:writing-plans` | `PLAN.md` | 18 个 task（T1–T17 + T3b），含完整 TDD 代码，5-PR 工作树表。 |
| 3 | §4.5 冷启动验证（两轮） | 见 `SPEC_PROCESS.md` §五 | 第一轮不合规（agent 自行改 bug 未停下询问，scope 滚到 10 task），清除重做；第二轮合规（Task4+Task8，停、引用、两解、未猜）。暴露 PLAN 3 处 bug 已修。 |
| 4 | `superpowers:subagent-driven-development` | 各 task 实现 + 评审 | 本日志 §3 逐 task 记录。 |
| 5 | `superpowers:finishing-a-development-branch` | PR-1 合并入 main | 见 §4。 |

---

## 2. 关键人工干预与裁决

| 时间点 | 议题 | 人工裁决 | 影响 |
|---|---|---|---|
| brainstorming | 重点维度 | 反馈闭环（乙），但追加"六维全有最低实现" | SPEC §A.4-D 双约束 |
| brainstorming | 失败指纹是否含 message | 不含（采纳 AI 主张） | Task 1 `failure_fingerprint` 设计 |
| 冷启动 R2 受阻点 #1 | `escape_regex` 默认值 | **甲**：升级为 `r"(^/)|(\.\.)"`（覆盖绝对路径 + 穿越），补 `test_absolute_path_needs_approval` | PLAN Task 2 修订 |
| 冷启动 R2 受阻点 #2 | Task 8 测试多余 import | **B**：删除 `from harness.feedback.validators import ...` | PLAN Task 8 修订 |
| PLAN 自评 F1 | 无真实 LLM provider client | 新增 Task 3b（DeepSeek + Anthropic over httpx） | PLAN 增 1 task |
| PR 收尾 | 5 PR vs 12 PR | 合并为 5 PR | 平衡 §4.6/§4.7 忠实度与编排成本 |
| PR-1 收尾 | 合并方式 | **合并入 main 本地**（origin/main 落后，无远程 PR 目标） | PR-1 fast-forward 入 main |

> 凭据红线（用户逐字保留）：key 绝不硬编码进源码、绝不提交进 Git（含历史）、绝不写入日志/终端 history/明文配置文件；.env 为明文、进程环境可见；view status 不得回显明文；仓库内不得出现任何真实凭据；CI 必须含名为 `unit-test` 的 job，最后一次 CI/CD 执行必须 pass。

---

## 3. Subagent-Driven Development 逐 task 记录

格式：Task / 实现者(模型) → commit / 评审者(模型) → Spec✅? Quality? / 关键发现。

### PR-1 基座（已合并入 main，main @ 0f57792）

| Task | 实现 commit | 评审 | 结果 |
|---|---|---|---|
| T1 models | `84ee16f` (haiku) | sonnet | Spec✅ Approved；Minor：缺尾换行、enum 风格、frozenset 未参数化 |
| T2 config | `37d2cdb` (haiku) | sonnet | Spec✅ Approved；⚠️PYTHONPATH=src 需显式（延迟到 T16 打包） |
| T3 LLM base+mock | `f5fb361` (haiku) | sonnet | Spec✅ Approved；§A.4-C 完整（mock 无网络/随机） |
| T3b provider clients | `0f57792` (haiku) | sonnet | Spec✅ Approved；凭据 clean（仅 fake `sk-test`）；6/6 离线 |
| PR-1 终评 | — | opus | READY TO MERGE；跨 task 类型一致；6 Minor 全延后（cosmetic） |

### PR-2 机制层（分支 pr-2-mechanisms，进行中）

| Task | 实现 commit | 评审 | 结果 |
|---|---|---|---|
| T4 guardrail | `4ee7d6b` (haiku) | sonnet | Spec✅ Approved；8 测试，full 19/19；凭据 clean |
| T5 approver | `29d6bc8` (haiku) | sonnet | Spec✅ Approved；AutoReject 零 I/O（§A.4-C） |
| T6 memory | `697604e` (haiku) | sonnet | Spec✅ Approved；JSON Lines + tag 交集，无向量库 |
| T7 validators | `1699a8e`→`ce8263c` (haiku, 含 fix round) | sonnet ×2 | Spec✅ Approved；**Important 修复**：`ModuleNotFoundError` 误归类为 ASSERTION_ERROR → 扩展判定 + 恢复真实 fixture + 锁定测试；re-review 确认解决 |
| T8 feedback_loop ★ | `889312d` (haiku) | sonnet | Spec✅ Approved；三大不变式（指纹不含 message / 停机优先级 / NO_PROGRESS 窗口）均成立 |
| T9 tools/dispatcher | `075da87` (haiku) | sonnet | Spec✅ Approved；⚠️`_safe` startswith 弱（plan-mandated，兄弟前缀可绕过）→ 延迟到 PR-2 终评裁决（1 行硬化 `base in target.parents`） |
| T11 credentials | `20521b9` (haiku) | sonnet（进行中） | 待评 |

---

## 4. 工作树与分支事件

- **PR-1**：工作树 `.claude/worktrees/pr-1-base`（分支 pr-1-base，从本地 HEAD `5b3e337` 起支，因 origin/main 落后）。PR-1 完成后用 `finishing-a-development-branch` fast-forward 合并入 main。
- **工作树重建事故**：PR-1 收尾时尝试 `git worktree remove pr-1-base`，因本会话 cwd 被钉在该路径，删除失败但已清空内部文件（含 `.git` 指针与 `.superpowers/sdd/` scratch）。恢复：删冗余分支，在原 pinned 路径重新 `git worktree add` 到新分支 `pr-2-mechanisms`（从 main `0f57792`）。代码与提交均安全（已入 main）；PR-1 的 SDD scratch（briefs/reports/reviews）丢失，本日志据上下文重建。
- **PR-2**：复用同一 pinned 工作树路径，分支 `pr-2-mechanisms`。子代理继承该 cwd，提交落 pr-2-mechanisms。
- **持久账本**：`.superpowers/sdd/progress.md` 置于主树（跨工作树重建存活）。

---

## 5. 待办（PR-3..PR-5 + 终交付物）

- PR-3 集成：T10 main loop、T12 mini 目标仓库（手写）、T13 集成测试。
- PR-4 WebUI+演示：T14 webui、T15 demo。
- PR-5 打包+CI：T16 packaging/CLI（含 `@pytest.mark.live` 真实冒烟，CI skip）、T17 `.gitlab-ci.yml`（必须含 `unit-test` job）。
- 终交付物：`README.md`（§5 章节）、`AGENT_LOG.md`（本文件，持续更新）、`REFLECTION.md`（1500–2500 字，学生手写）、全项目终评 code review。

> 本文件随 SDD 进展滚动更新；每 PR 合并后追加该 PR 的终评结论。
