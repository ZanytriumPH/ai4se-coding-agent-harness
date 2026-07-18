# SPEC_PROCESS.md · Coding Agent Harness

> 记录与 Superpowers 协作生成 SPEC/PLAN 的过程，以及**冷启动验证**的完整发现。对应通用要求 §4.4（过程文档）与 §4.5（冷启动验证）。

---

## 一、Brainstorming 关键节点

`superpowers:brainstorming` 技能以一次一问的苏格拉底式追问，把"造一个 Coding Agent Harness"从模糊想法推到可执行 SPEC。以下是追问中**让我修正原设想**的关键节点：

| # | 追问 | 我原设想 | 修正后 |
|---|---|---|---|
| Q1 | 端到端演示的是什么编码任务？ | 含糊"能修代码" | 收敛为**多文件修复任务**（B）：给带失败测试/lint/类型错的小仓库，agent 自主修复。范围甜区——非玩具、机制形态最清晰 |
| Q2 | 六维选哪个做深？ | 想全做浅 | 定**反馈闭环**为重点：修复任务每一步都依赖客观反馈，且天然把校验器→分类→停机→回灌串成全代码链，最契合 §A.4 (A)(B)(C) |
| Q4 | 接哪家 LLM？ | 默认 Anthropic | 因国内可用性改为**DeepSeek 默认、Anthropic 可选**；单测一律用 Mock，不依赖网络 |
| Q8 | 分发与凭据存哪？ | 想做 Docker | 改为**PyPI+OS 钥匙串**：与 Windows/Python/CLI-HITL 天然契合，凭据做到"最好形态"而非凑合 |
| Q9 | §5.9 硬要求 WebUI，与 CLI-HITL 冲突 | 只做 CLI | 接受**WebUI 为主交互面**，并把审批抽成 `Approver` 接口（Cli/Web/AutoReject 三实现），使 WebUI 成为内核外薄层不污染 §A.4-C 判据 |

---

## 二、至少 3 轮关键迭代的对话节选与处理决策

### 迭代 1：重点维度之争（反馈闭环 vs 治理）
- **AI 提议**：反馈闭环为 main contribution，理由是修复任务里反馈信号出现频率最高、且演示三幕有两幕可落在其上。
- **我的决策**：采纳。但我**追加约束**——治理虽非重点也必须有可运行最低实现（§A.4-D），不能因"做深反馈"而让治理缺位。AI 同意并写入 §A.4-D 的"基础要完整"。
- **学到的**：main contribution 与最低实现是两件事，SPEC 要同时表达"深一处、全六维不缺"。

### 迭代 2：失败分类法——封闭枚举 vs 开放标签
- **AI 提议**：`FailureKind` 用封闭枚举，agent 据此选修正策略、可确定性单测；开放标签会让分类依赖 LLM 智能、一旦离开 LLM 即不可测，按 §A.4-C 不算机制。
- **我的决策**：采纳封闭枚举。我**追问**了"无进展检测的指纹要不要含 message"——AI 主张**不含**（message 文本变化会让"实质无进展"被误判为"有进展"），我接受。这条后来被冷启动验证间接佐证为关键设计。

### 迭代 3：WebUI 与 §A.4 红线的张力
- **我提出顾虑**：§5.9 硬要求 WebUI，但 §A.4 要求内核自编码、WebUI 会不会污染"移除 LLM 后机制可单测"判据？
- **AI 提议**：把审批做成 `Approver` 接口，`WebApprover` 是内核外薄层，单测注入 `AutoRejectApprover`，判据对内核仍成立。
- **我的决策**：采纳，并在架构图里**显式划线**："WebUI = 内核外薄层，不参与 mock 单测"。这是整个 SPEC 里我最在意的一处边界——它决定了交付物不被前端工作量稀释机制工作量。

---

## 三、哪些建议是 AI 提出而我采纳 / 推翻或修正

**采纳（AI 提议，我接受）：**
- 反馈闭环为重点维度（Q2）
- 失败指纹不含 message（迭代 2）
- `Approver` 接口隔离 WebUI（迭代 3）
- 技术栈 Python + harness 与目标仓库同语言（Q3）
- `keyring` in-memory fake 注入单测（Q 凭据）

**推翻或修正（我改了 AI 的原提议）：**
- LLM 供应商：AI 默认推荐 Anthropic，我**因国内可用性推翻**为 DeepSeek 默认。
- 分发：AI 列了 Docker 为主选项，我**选 PyPI+钥匙串**，理由是凭据威胁模型更干净、HITL 交互更顺。
- 重点维度的连带约束：AI 只说"选一个做深"，我**修正**为"做深反馈闭环 + 六维全有最低实现"，避免治理/记忆/工具缺位。
- escape_regex（冷启动第二轮发现）：AI（主开发，本轮我）建议 `r"(^/)|(\.\.)"`，冷启动 agent 与用户先选了 `r"\.\./"`；我**指出后者漏掉绝对路径、与 SPEC §3.5 字面冲突**，最终裁决为**甲（`r"(^/)|(\.\.)"` + 补绝对路径测试）**。

---

## 四、对 brainstorming 技能的反思

**做得好的：**
- "一次一问 + 多选优先"让每步决策都小而可验证，避免一上来就写大段设计。
- 它强制在 §A.4-C 判据上反复对齐（"移除 LLM 后还剩多少可独立验证的工程"），这是本项目最容易松懈的红线，技能守住了。
- 苏格拉底式追问把"WebUI 与 §A.4 红线的张力"这类我自己没第一时间想到的冲突逼出来。

**让我不满的：**
- brainstorming 技能默认把 SPEC 存到 `docs/superpowers/specs/`，但本项目要求文件名为根目录 `SPEC.md`——技能与课程要求的命名/路径不一致，需手动覆盖。
- 技能不主动检查"PLAN 代码片段的跨语言转义正确性"（如 Python raw string vs YAML 字符串），这类问题只能靠冷启动暴露——下文第二轮即栽在此。
- 技能偏"设计与确认"，对"PLAN 代码示例是否真能跑通"无内置校验，留下一个"看起来完整但含 bug 的 PLAN"风险。

---

## 五、冷启动验证（§4.5）

### 5.1 两轮验证概览

| 维度 | 第一轮 | 第二轮 |
|---|---|---|
| 验证代理 | GitHub Copilot (DeepSeek) | 另一不同类型 agent |
| 选定 task | 声称 Task 9+10，实际做了 T1–T10 | Task 4 + Task 8（+ T1/T2 最小脚手架） |
| 是否停下询问 | ❌ 未停，直接自行改 bug | ✅✅ 停下、逐字引用、给两种解读、未写代码等裁决 |
| 范围声明 vs 实际 | 不一致（声称 2 task 实做 10） | 一致（仅 T4+T8+脚手架） |
| §4.5 合规性 | 不合规（违反"不猜测"硬要求） | **合规** |

第一轮因 agent 未按"遇不确定即暂停询问、而非凭猜测继续"操作，判定为**不合规**，已清除其产物重做。第二轮合规，下文记录第二轮发现。

### 5.2 第二轮：受阻点与裁决

**受阻点 #1：`escape_regex` 默认值让 `test_normal_write_allowed` 必败**
- 原文：`escape_regex: str = r"\.\./|/"`（Task 2）
- 困惑：正则 `\.\./|/` =「`../` 或 `/`」，`re.search` 命中任意含 `/` 路径，`src/app.py` 被判 `NEED_APPROVAL` 而非 `ALLOW`。
- 裁决：**A——PLAN 写错**。但进一步判定：上一轮的 `r"\.\./"` 仍不够（漏绝对路径，与 SPEC §3.5「绝对路径 → NeedApproval」冲突）。最终采用 `r"(^/)|(\.\.)"`（覆盖绝对路径 + 穿越），并新增 `test_absolute_path_needs_approval` 锁定意图。
- 判定：**PLAN 写错，agent 读得没错**。

**受阻点 #2：Task 8 测试 import 了范围外的 Task 7 符号**
- 原文：`from harness.feedback.validators import Product, PytestValidator, RuffValidator, MypyValidator`（Task 8 测试）
- 困惑：4 个符号定义在 Task 7（不在本次范围），且 4 个测试函数均未使用，但 import 阶段即 `ModuleNotFoundError`。
- 裁决：**B——删除该 import 行**。不建 Task 7 脚手架（那会为满足一个未使用 import 去实现范围外工作，违反 scope）。
- 判定：**PLAN 写错（多余 import）**。

### 5.3 第二轮：产出 vs 预期

- 预期：Task 4（7 测试）+ Task 8（4 测试）= 11 测试全绿。
- 实际：创建 9 文件，11/11 测试通过（独立 `pytest` 复跑确认）。未 `git commit`（按要求）。超 Task 4+8 范围的一律未实现。
- 差距：无功能性差距；仅 PLAN 两处缺陷（已修）。

### 5.4 据 cold-start 修订的 SPEC/PLAN diff

| 文件 | 修订前 | 修订后 | 根因 |
|---|---|---|---|
| `PLAN.md` Task 2 config.py 默认 | `escape_regex: str = r"\.\./\|/"` | `escape_regex: str = r"(^/)\|(\.\.)"` | 误匹配任意 `/`，且补绝对路径 |
| `PLAN.md` Task 2 config.py load 默认 | `r"\.\./\|/"` | `r"(^/)\|(\.\.)"` | 同上 |
| `PLAN.md` Task 2 config.yaml | `"\\.\\./\|/"`（YAML 双引号转义非法） | `'(^/)\|(\.\.)'`（YAML 单引号） | YAML 转义 + 正则语义双重错 |
| `PLAN.md` Task 2 测试 cfg_text | 同上双引号 | 同上单引号 | 同上 |
| `PLAN.md` Task 8 测试 | 含 `from harness.feedback.validators import ...` | 删除该行 | 多余 import 引用范围外模块 |
| `PLAN.md` Task 4 测试 | 7 测试 | + `test_absolute_path_needs_approval`（8 测试） | 锁定绝对路径→NeedApproval 意图 |

### 5.5 冷启动反思

1. **"停下询问而非凭猜测继续"是 §4.5 的命门**——第一轮 agent 直接改 bug 而不问，使验证沦为"agent 自我修复"而非"暴露 spec 缺陷"；第二轮强制此规则后，缺陷暴露质量显著提升。
2. **冷启动 agent 倾向越界**：第一轮把 scope 从 2 task 滚到 10 task；第二轮靠提示词显式 scope 约束（"仅 T4+T8 + 最小脚手架，其余一律不做"）才守住。提示词必须硬约束 scope。
3. **PLAN 的代码片段不是圣经**：两轮共暴露 3 类 PLAN bug（正则语义、分类逻辑、跨语言转义），皆非 SPEC 语义错而是 PLAN 落地错。说明 writing-plans 技能产出的"完整代码"仍需冷启动作为客观试金石。
4. **最大价值**：冷启动是单人项目中最接近"同侪评审"的机制——它把"你和主 agent 沉淀的隐性上下文"显式化为"陌生 agent 受阻处"，这些受阻处即 spec 质量最有价值的反馈信号。
5. **不足**：即便第二轮，agent 仍选了欠完备的 `r"\.\./"`——需主开发（人）据 SPEC §3.5 字面裁决升级为 `r"(^/)|(\.\.)"`。说明冷启动暴露"PLAN 可执行性"，但"PLAN 是否忠实于 SPEC 语义"仍需人工把关。
