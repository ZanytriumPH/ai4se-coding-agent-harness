# REFLECTION.md · Coding Agent Harness

> 学生本人反思报告 | AI4SE 期末项目 A
>
> 本项目用 Superpowers 方法论从零构建了一台 Coding Agent Harness。以下反思基于 18 个 task、7 个 PR、77 个离线单测的完整开发过程，对方法论做出批判性回顾。
>
> 本反思日志有使用 AI 辅助润色，但所有陈述均为本人独立思考的结果。

---

## 一、哪些 Superpowers 技能发挥了最大作用？哪些"形式大于实质"？

真正改变了产出的技能有三个。

**brainstorming** 的一次一问苏格拉底追问，把 "造一个 harness" 收敛为 9 个可执行决策：目标场景、重点维度、LLM 供应商、分发形态、WebUI 与内核的隔离边界。没有这个技能，我会直接跳去写代码，而不会在 "失败指纹要不要含 message" "WebUI 会不会污染判据" 这些设计问题上花时间。后来的开发证明，这些前期决策决定了机制的可测性与内核纯度。

**subagent-driven-development**（SDD）是整条实现链的骨架。18 个 task，每个派新鲜子代理完成，再由另一模型做两阶段评审。子代理忠实按 PLAN 转录，评审代理捕获偏离 —— Task 7 的 `ModuleNotFoundError` 误归类就是评审在 fix round 里揪出来的。

**test-driven-development** 在本项目里更像是 "安全网" 而非 "设计驱动"。PLAN 已把测试代码写好，子代理只是转录 + 跑通，TDD 退化为验证转录正确性。但在 bug 修复阶段它仍是不可替代的放大器，如 collection 误报 PASS、loop outcome 误导、审计不准、validator KeyError，每一个都是先写失败测试再修，确保修复不引入回归。

**形式大于实质的**：`using-git-worktrees`。本意是每个 PR 一个独立 worktree 隔离工作区，但实际执行中，PR-1 收尾时 `git worktree remove` 因会话 cwd 钉在该路径而失败，还清空了内部文件（SDD scratch 丢失）。之后被迫在同一个 pinned 路径上切换分支复用工作树，这已经偏离了 "每个 PR 一个 worktree" 的字面要求。worktree 在本项目里更像是 "仪式" 而非 "使能器"。

---

## 二、TDD 强制在 AI 协作下是阻碍还是放大器？

在 task 实现阶段，PLAN 已含完整测试代码，子代理只是转录——真正的设计驱动被前置到 PLAN 阶段。但在 bug 修复阶段，TDD 是不可替代的放大器。终评发现的 PytestValidator collection 误报 PASS 最典型：先构造 `pytest_collection_error.json`（空 `tests` + 失败 `collectors`）→ 红灯 `verdict=PASS, failures=[]` → 最小修复（扫 `collectors` 产出 `COLLECTION_ERROR`）→ 绿灯。没有 TDD，这个边界条件几乎不可能被想到——mock LLM 下的 demo 从不触发 collection 崩溃路径。

所以我的结论是：**当 PLAN 已含测试时，TDD 退化为安全网；但安全网本身在多人/多代理协作中价值巨大**——它保证了 77 个测试在每一轮修复后仍然全绿，没有回归。这不是 "形式大于实质"，而是 "实质从设计阶段转移到了验证阶段"。

---

## 三、subagent-driven 能让智能体自主运行多久而不偏离主题？

本项目给出了一个具体的边界值：**Task 17**。当父会话跑到第 17 个 task 时，上下文累积触发 32MB 上限，子代理评审无法返回，`/compact` 本身也因 attached media 超限而失败。这就是 "自主运行边界" 的实测值。

边界不是 task 数，而是**上下文体积**。每个 task 的 brief + 子代理输出 + 评审报告 + commit diff 在父会话里累积，到 PR-5 收尾阶段必然超限。过界后的回退是 inline 评审——核对 §5.6/§3.2 要求，判定 15 行 yaml clean，已记录偏离（AGENT_LOG §9）。

更深层的问题是：**SDD 方法论假设上下文能容纳整条开发链**。这个假设在中等规模项目已不成立。如果重做，我会每个 PR 合并后立即 `/compact`，AGENT_LOG 改为 PR 收尾批量写入。

---

## 四、SPEC/PLAN 质量如何影响实现质量？举一个具体案例。

最典型的案例是 **Task 7 `ModuleNotFoundError` 归类偏差**。

PLAN 为 `PytestValidator` 写的 brief 里，fixture 用了 `ModuleNotFoundError` 作为测试输入，但分类谓词是 `"Import" in ctype`。`ModuleNotFoundError` 的 `ctype` 字面是 `"ModuleNotFoundError"`——不含子串 `"Import"`，于是 `"Import" in "ModuleNotFoundError"` 为 `False`，错误被归类为 `ASSERTION_ERROR` 而非 `IMPORT_ERROR`（call 阶段修复；collection 阶段空 tests→`COLLECTION_ERROR` 是另一处独立修复）。

这个不一致是 brief 的自相矛盾，fixture 和谓词是我（借 AI）写的，但我在写的时候没有自检 "测试预期与此实现是否自洽"。子代理忠实转录后，评审在 fix round 才识别——它扩展了谓词 + 恢复了真实 fixture + 锁定了测试。

这个案例揭示了 SDD 的关键性质：**subagent 忠实转写时，不是 "放大" 而是 "暴露" brief 的不一致**。子代理不会质疑 brief，自相矛盾被原样转为代码 bug。这要求 PLAN 质量比手写代码时更高，手写时你会在编码过程中发现设计问题，SDD 把 "写代码" 外包后，问题只在评审阶段浮现。

冷启动暴露的 `escape_regex` 误匹配是同类问题（详见 §六假设 4）。教训：**PLAN 里每段代码都须自检 "测试预期与此实现是否自洽"**，writing-plans 技能不做此校验，需人工补位。

---

## 五、凭据与分发这两条工程要求，迫使你想清楚了哪些原本会忽略的问题？

最典型的是三条：

**`status()` 不回显明文**。这是 "被要求逼出来才想到" 的。最初我只计划做 keyring 存储 + 隐藏输入，但 §3.1 明确要求 "查看状态时不得回显明文"。这迫使我设计了 `status()` 只返回 `configured` / `not configured` 两个枚举值，并在测试里锁定，`FakeKeyring` 注入后断言 `status()` 输出不含已存密钥明文。没有这条要求，我大概率会做一个 "显示 key 的前 4 位 + 后 4 位" 的半透明方案——看起来安全，实则暴露了部分明文。

**`testpaths` 让裸 pytest 不误收 demo 测试**。demo 的 `target_repo` 有 seeded-failure 测试，从仓库根跑 `pytest` 会误收。"一键 `make test` 必须通过"这条分发要求迫使我想清楚 scope 隔离，`pyproject.toml` 设 `testpaths=["tests"]`。

**PyPI + OS 钥匙串与 Docker 互斥**。PyPI 为主分发依赖 OS 钥匙串——容器内不可用。Docker 降级为"可选演示"，README 标注了此限制。分发形态的选择反过来约束了凭据方案。

---

## 六、对 Superpowers 方法论的批判——它假设了什么？这些假设在本项目里成立吗？

Superpowers 至少隐含了四个假设，在本项目里**全部受到挑战**：

**假设 1：可自由 create/remove worktree**。本项目中，会话 cwd 被 harness 钉在 worktree 路径，`git worktree remove` 失败并清空内部文件。此后被迫复用同一 pinned 路径切换分支。这个假设不成立。

**假设 2：上下文足够容纳整条 SDD 链**。Task 17 时触发 32MB 上限，子代理评审无法返回，必须在方法论层面提供溢出回退策略，而非假设它不会发生。

**假设 3：commit/PR 工作流有远程 PR 目标**。所有 7 个 PR 都是本地分支 ff-merge 入 main，origin 落后、没有远程 PR、没有平台级 review。CI pass 只能在 push 后才成立——开发过程与交付要求之间存在落差。我是在本地 "模拟" 了 PR 工作流，而非真正走通。

**假设 4：PLAN 自洽**。冷启动暴露 3 处 PLAN 代码片段的自相矛盾。writing-plans 技能不内置 "PLAN 代码示例是否自洽" 的校验，这个缺口只能靠冷启动 + 人工评审补位。

这些假设并非 Superpowers 独有。但本项目的实测表明，**四个假设在单人+中等规模+本地开发场景下全部受挑战**。方法论的价值不在于假设了什么，而在于它嵌入的应对机制——冷启动验证、定期 compact、显式记录偏离，在假设被打破时兜底。

---

## 七、过程级盲点

**盲点 1："subagent 写代码" vs "核心应自写" 的张力**。诚实地说：本项目 harness 内核——`AgentLoop.run()`、`failure_fingerprint`、`feedback_loop.update`、`guardrail.inspect`、`_safe`——全部由子代理按 PLAN 转录写出。我自己手写仅三处：(1) 冷启动后 `escape_regex` 裁决；(2) PR-2 `_safe` 硬化；(3) Task 16 CLI §3.1 充实。代码约 95% 由 AI 转录、5% 由我修正——这是 SDD 的真实面貌。

**盲点 2：六维"最低实现"的边界判断**。我做深了反馈闭环——封闭枚举 + 指纹不含 message + 三种停机 + Validator 鲁棒性。但治理护栏（HITL 状态机 + 三 Approver 实现 + 声明式规则集）其实也不薄。回头审视，治理的深度是否悄悄从反馈闭环"漏"了过来？

**盲点 3：最有效的 prompt 策略——"停下询问"措辞定行为**。冷启动第一轮 agent 自行改 bug 越界，不合规；第二轮把"遇不确定必须停下询问、逐字引用、两解、不写"写进提示词后合规。两轮对照证明提示词措辞决定行为。这与 §A.4-C"提示词算内容物不算机制"有张力——冷启动作为 spec 质量证据的有效性，本身依赖 prompt 工程。

**盲点 4："spec 优于 brief"是否总对**。三处甲裁决本质是在两份自己借 AI 写的文档之间选一个。是否有 brief 反而更具体、更该胜出的时刻？本项目未遇到，但追问比"甲裁决"本身更值得反思。

**盲点 5：Open Design/Material 前端——投入与可计分产出的错位**。PR-4 是最大非机制块——Starlette SSE、Material CDN、`config.yaml`——按 §A.4-C 全算"内容物"不计入机制工作量。投入与可计分产出之间存在诚实的错位。

---

## 八、如果重做我会改变什么？

1. **PLAN 自检 + 上下文管理**：writing-plans 后逐 task 自检"测试预期与实现是否自洽"；每个 PR 合并后立即 `/compact`，AGENT_LOG 改为 PR 收尾批量写入——这两条分别拦截冷启动 3 处 bug 和 32MB 溢出。
2. **真实冒烟前置**：PR-3 内核完成后就接入真实 LLM 跑端到端——"机制确定性"与"真实通路"之间的缺口应早暴露，而非留到可选项。
