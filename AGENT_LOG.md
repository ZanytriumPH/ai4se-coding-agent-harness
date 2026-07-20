# AGENT_LOG.md · Coding Agent Harness (AI4SE 期末项目 A)

> 过程日志：记录开发过程中触发的 Superpowers 技能、子代理提交、人工干预与裁决。对应通用要求 §4.9（每条含：时间/task 编号、触发技能、prompt/context 配置、commit hash、人工干预、学到的教训）。

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
| PR-2 收尾 | `_safe` 兄弟前缀弱点（plan-mandated Important） | **甲：硬化** `base in target.parents` + 回归测试 | 与冷启动 `escape_regex` 甲同型（spec §3.3 优于 brief） |
| Task 7 fix | `ModuleNotFoundError` 归类 | 扩展 predicate（`"Import" in name`）+ 恢复真实 fixture + 锁定测试 | brief 自相矛盾（fixture 用 ModuleNotFoundError 但谓词不匹配），agent 在 fix round 内识别并修 |
| Task 14 | WebUI 前端 Open Design 落地（§3.6 强烈推荐非强制） | **甲：点名 + CDN 实引 Material**（SPEC §8 + index.html CDN） | WebUI 仍为内核外薄层，不稀释机制工作量 |
| Task 16 | CLI 仅 `--init-key`（brief 对 §3.1 不足） | 充实为 §3.1 完备（`--status`/`--update-key`/`--clear-key` + `.env` loader） | spec §3.1 优于 brief，与 `_safe`/`escape_regex` 同型 |
| Task 17 | 评审方式 | **inline 评审**（非子代理） | 会话上下文触发 32MB 上限，子代理无法返回；15 行 yaml 主代理核对 §5.6/§3.2 |
| PR-6 | 真实 LLM 端到端跑通（§A.4-C 盲点 2） | 主代理 inline 真实跑调试 + TDD，非 SDD subagent | 真实跑暴露 8 个 mock 不可见 bug，逐个红测试修复；failures 4→0 success |
| PR-6 | run_tests 用 `python -m pytest` 而非控制台脚本 | **甲：按 pytest 官方推荐** | 控制台脚本不把 workdir 入 sys.path → collection ImportError（假反馈）；与 spec 优于 brief 同型（规范要求优于便利默认） |
| PR-6 | system_prompt 措辞定行为（盲点 4） | 强化：run_tests 优先 / repo-relative 路径 / 禁 exec_shell 调 path | 冷启动"prompt 措辞定行为"裁决在真实跑复现并固化 |
| PR-7 | 补 G1（cli 接真实跑 + 模块级 app）/ G2（Dockerfile）是否 spec 变更 | **非 spec 变更**：补齐 SPEC 既定 CLI 入口 + README 对齐；与 `approve_all_writes`（spec §3.5 扩展，已拒）区分 | scope 边界——README overclaim 是债，补入口是还债不是扩面 |
| PR-7 | demo 脚本与 cli 关系 | **反转**：真实跑逻辑只入 `harness.cli`，demo/run_live+run_webui 转薄包装委托 | 依赖方向正确（demo→harness），两入口不漂移 |

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

### PR-2 机制层（已合并入 main，main @ 0d76d87）

| Task | 实现 commit | 评审 | 结果 |
|---|---|---|---|
| T4 guardrail | `4ee7d6b` (haiku) | sonnet | Spec✅ Approved；8 测试，full 19/19；凭据 clean |
| T5 approver | `29d6bc8` (haiku) | sonnet | Spec✅ Approved；AutoReject 零 I/O（§A.4-C） |
| T6 memory | `697604e` (haiku) | sonnet | Spec✅ Approved；JSON Lines + tag 交集，无向量库 |
| T7 validators | `1699a8e`→`ce8263c` (haiku, 含 fix round) | sonnet ×2 | Spec✅ Approved；**Important 修复**：`ModuleNotFoundError` 误归类为 ASSERTION_ERROR → 扩展判定 + 恢复真实 fixture + 锁定测试；re-review 确认解决 |
| T8 feedback_loop ★ | `889312d` (haiku) | sonnet | Spec✅ Approved；三大不变式（指纹不含 message / 停机优先级 / NO_PROGRESS 窗口）均成立 |
| T9 tools/dispatcher | `075da87`→`0d76d87` (haiku + fix) | sonnet ×2 | Spec✅ Approved；⚠️`_safe` startswith 弱（兄弟前缀可绕过，plan-mandated）→ 人工裁决**甲：硬化** `base in target.parents` + 回归测试 |
| T11 credentials | `20521b9` (haiku) | sonnet | Spec✅ Approved；CredentialStore(keyring)+FakeKeyring 注入；`status()` 不回显明文 |
| PR-2 终评 | — | opus | CHANGES NEEDED→READY TO MERGE（_safe 甲裁决后）；8 Minor 全延后 |

### PR-3 集成（已合并入 main，main @ ea31f0e）

| Task | 实现 commit | 评审 | 结果 |
|---|---|---|---|
| T10 main loop ★ | `2d6b330` (sonnet) | sonnet | Spec✅ Approved；§A.4-A 自实现循环（无框架寄生）；1 测试 = §A.6 幕②；full 43/43 |
| T12 mini target repo | `eaf6908` (haiku) | sonnet | Spec✅ Approved；手写（§六 标注）；4 fail/3 lint/3 type，真实可修 |
| T13 integration | `ea31f0e` (haiku) | sonnet | Spec✅ Approved；真实机制栈 + MockLLM；§A.6 幕② 真实 fixture 变体；full 44/44 |
| PR-3 终评 | — | opus | READY TO MERGE；内核完整，§A.4-A/B/C 全确认；⚠️ testpaths gap 延后 T16（已修） |

### PR-4 WebUI+演示（已合并入 main，main @ 50d88cc）

| Task | 实现 commit | 评审 | 结果 |
|---|---|---|---|
| T14 webui | `6ec8165` (sonnet) | sonnet | Spec✅ Approved；Starlette SSE+approval；§3.6 甲（Material CDN）；§A.4-C 隔离；full 45/45 |
| T15 demo | `50d88cc` (haiku) | sonnet | Spec✅ Approved；§A.6 三幕 ALL ACTS PASS（mock 离线）；full 45/45 |
| PR-4 终评 | — | opus | READY TO MERGE；§A.6 项目级满足、§A.4-C WebUI 隔离、§3.6 甲、部署就绪 |

### PR-5 打包+CI（已合并入 main，main @ 63c7a2b）

| Task | 实现 commit | 评审 | 结果 |
|---|---|---|---|
| T16 packaging/CLI | `f3ecfe4` (sonnet) | sonnet | Spec✅ Approved；pyproject(testpaths 修 gap)+Makefile+§3.1 充实 CLI；make test→45/45, make demo→ALL ACTS PASS |
| T17 .gitlab-ci.yml | `d3f0356` (haiku) | **主代理 inline**（⚠️ 见 §9） | clean；§5.6 unit-test job + §3.2 build-wheel；CI 用 `pytest -q` 经 testpaths scope |

### PR-6 真实 LLM 端到端（已合并入 main，commit `356bd84`，详见 §9b）

非 SDD subagent task；主代理 inline 真实跑调试 + TDD（每 bug 先红测试再修）。真实 LLM（DeepSeek）驱动暴露 8 个 mock 不可见 bug：

| 修复 | 测试 | 现象 → 根因 |
|---|---|---|
| loop 硬 turn 上限 | `test_loop_hard_turn_cap_bounds_non_validator_loop` | `max_rounds` 只数校验轮，`read_file` 循环跑 323 轮不封顶 |
| tool-use 协议合规 | `test_loop_builds_tool_use_protocol_messages` | 不回显 assistant tool_call + 结果用 `user` 角色 → LLM 300x 读同一文件 |
| `tool_call_id` 捕获 | （含上） | `llm/base.py` + `deepseek.py` 捕获 id |
| 6 工具 schema | `test_tools_schema` (7) | loop 传 `tools_schema=[]` → 真实 LLM 无工具定义 |
| `python -m pytest` | `test_run_tests_invokes_python_minus_m_pytest` | 控制台脚本不把 workdir 入 sys.path → 3 collection ImportError，`app.py` 从未加载 |
| JSON 报告写临时文件 | `test_run_tests_reads_json_from_report_file` | `--json-report-file=-` 写字面文件 `-`，stdout 非 JSON 崩 |
| validator 容非 JSON | `test_pytest_validator_nonjson_stdout_does_not_crash` | 脏 stdout 崩整个 loop → 降级 FAIL+UNKNOWN |
| utf-8/replace 解码 | `test_runners_encoding` (3) | 中文 locale GBK 解码 reader 线程崩 |
| Windows 绝对路径 guardrail | `test_guardrail` windows×2 | `C:\` / UNC 漏过 NEED_APPROVAL（POSIX `^/` 不一致） |

结果：DeepSeek-chat，12 轮，failures 4→1→0，outcome=**success**。70/70 单测 + mock 三幕 demo 全绿。

### PR-7 CLI 真实跑 + 模块级 app + Dockerfile（已合并入 main，commit `34003a1`，详见 §9c）

非 SDD subagent task；主代理 inline 补 G1+G2（最终合规矩阵暴露的代码侧缺口）+ TDD：

| 修复 | 测试 | 现象 → 根因 |
|---|---|---|
| cli.py 接真实跑 | `test_cli_headless_*` | stub `print("not implemented")` → README 第 78 行 `harness --workdir` 不工作 |
| `--run-webui` 子命令 | （冒烟） | run_webui 逻辑只在 demo 脚本，CLI 无浏览器 HITL 入口 |
| `_build_loop` 共享布线 | `test_build_loop_wires_*`（deepseek+anthropic） | 终端/真实-webui 各自布线会漂移 → 抽共享点仅 approver/on_turn 不同 |
| `_build_mock_loop` | `test_build_mock_loop_*` | 免 token webui 演示需复用脚本（绝对路径触发审批） |
| 模块级 `app` | `test_module_level_app_exists_for_uvicorn_deploy` | `make_app(session)` 非模块级 → `uvicorn webui.server:app` 报无属性 |
| Dockerfile + .dockerignore | （构建态） | README §分发 写 `docker build` 但无 Dockerfile；.env 需排除免进镜像层（§3.1） |

结果：76/76 单测；WebUI mock 往返冒烟（/pending→/approve→/events 全链路）。README 不再 overclaim。

---

## 4. 工作树与分支事件

- **PR-1**：工作树 `.claude/worktrees/pr-1-base`（分支 pr-1-base，从本地 HEAD `5b3e337` 起支，因 origin/main 落后）。PR-1 完成后用 `finishing-a-development-branch` fast-forward 合并入 main。
- **工作树重建事故**：PR-1 收尾时尝试 `git worktree remove pr-1-base`，因本会话 cwd 被钉在该路径，删除失败但已清空内部文件（含 `.git` 指针与 `.superpowers/sdd/` scratch）。恢复：删冗余分支，在原 pinned 路径重新 `git worktree add` 到新分支 `pr-2-mechanisms`（从 main `0f57792`）。代码与提交均安全（已入 main）；PR-1 的 SDD scratch（briefs/reports/reviews）丢失，本日志据上下文重建。
- **PR-2**：复用同一 pinned 工作树路径，分支 `pr-2-mechanisms`。子代理继承该 cwd，提交落 pr-2-mechanisms。
- **持久账本**：`.superpowers/sdd/progress.md` 置于主树（跨工作树重建存活）。

---

## 5. 待办（终交付物，学生侧 / 部署侧）

- ✅ PR-1–PR-7 全部合并入 main，77/77 离线单测 + §A.6 三幕 demo ALL ACTS PASS + 真实 LLM 端到端 success（PR-6 `356bd84`，详见 §9b；PR-7 `34003a1` 详见 §9c）。
- ✅ `REFLECTION.md`（§5.8）：学生本人撰写（§六标注 AI 辅助润色）；数字 5→7 PR / 50→77 测试经学生授权校准，观点未改。commit `9307b3a`。
- ✅ 线上部署 URL + 可访问 WebUI（§5.9）：部署于 **Railway**（连 GitHub 镜像 → 读 Dockerfile 构建），公网 URL `https://coding-agent-harness-production.up.railway.app/`。Dockerfile 默认 CMD 驱动 mock 修复循环（`python -m harness.cli --run-webui --mock`，读 `${PORT:-8000}`），公网实测三幕全跑通（run_tests fail → 审批卡 → run_tests pass → RUN RESULT）。不烘焙 key（§3.1）。镜像前全历史凭据扫描无命中。
- ✅ CI/CD 最后一次 pass（§5.7）：PR-6 push origin（`d749a27..6794a66`）后 GitLab 流水线通过——`unit-test` + `build-wheel` 均 pass。
- ✅ 真实 LLM 冒烟（§9.4，可选）：PR-6 已跑通——DeepSeek 12 轮 failures 4→0 success。`pytest -m live` 标记仍可选补为回归守卫。

> 代码侧交付完成；剩余为本人反思与部署动作。

---

## 6. PR-2 收尾（机制层）合并记录

- **合并方式**：`finishing-a-development-branch` → Option 1 合并入 main 本地（fast-forward，0f57792..0d76d87，9 commits）。main 上 42/42 测试通过。与 PR-1 同型（origin/main 落后，无远程 PR 目标）。
- **分支管理**：pinned 工作树复用——在同一 cwd 路径 `git checkout -b pr-3-integration`（从 main 0d76d87），删 pr-2-mechanisms 分支。未重建工作树（PR-2 sdd scratch 保留）。
- **人工裁决（甲）**：Task 9 `_safe` 兄弟前缀弱点。终评标为唯一阻断项（plan-mandated Important）。人裁决"甲：硬化"——将 `str(target).startswith(str(base))` 改为 `target != base and base not in target.parents` + 兄弟前缀回归测试。与冷启动 `escape_regex` 甲裁决同型（spec §3.3 优于 brief）。fix commit `0d76d87`，re-review 确认阻断项解决、PR-2 READY TO MERGE。
- **过程缺口补修**：§4.7 PLAN.md 持续更新——回填 11 个已完成 task 的 checkbox + commit hash（commit `5c213eb`）。
- **延期 Minor（PR-2）**：8 项（缺尾换行、Validator.parse 非抽象、ruff/mypy 下标 KeyError 风险、clear() 吞异常、verdict.name 字符串比较、FeedbackLoop.validators 未用、bare dict、Tool 非抽象）→ 全延后，PR-3 typing-polish 或 PR-5 finalize 一并清。
- **凭据**：全程 clean，仅 fake 占位（`sk-test`/`sk-secret`），`.gitignore` 排除 `.env`/`*.key`/`secrets.yaml`，`status()` 不回显明文。

---

## 7. PR-3 收尾（集成）合并记录 — 内核完成

- **合并方式**：`finishing-a-development-branch` → 合并入 main 本地（fast-forward，0d76d87..ea31f0e，4 commits）。沿用既定 5-PR 本地策略（PR-1/PR-2 同型，不再重复问）。main 上 `PYTHONPATH=src pytest tests/ -q` → 44/44（须 scope 到 tests/，见下）。
- **内核完成里程碑**：PR-3 后 harness 内核完整——`AgentLoop`（自实现主循环，无 LangChain/AutoGen/CrewAI/openai/anthropic 寄生）把所有机制（LLMClient/Guardrail/Approver/ToolDispatcher/Validators/FeedbackLoop/Memory/Config）串成 `while` 循环。§A.4-A/B/C 三判据全部确认（终评 opus）：(A) 自实现循环+mockable LLM 抽象；(B) 机制皆代码（guardrail.inspect/approver.approve/dispatcher.exec/validator.parse/loop.update/failure_fingerprint，LLM 只产下一步 Action）；(C) 移除真实 LLM 仍 44/44 离线可测（MockLLM+stub dispatcher+AutoReject+Memory on tmp_path，无网络/keyring/subprocess）。
- **§A.6 机制演示三幕覆盖**：① 护栏拦截危险动作 = Task 4 `test_guardrail.py`；② 反馈闭环驱动自我修正 = Task 10 `test_loop.py` + Task 13 `test_integration.py`（真实机制栈）；③ 重点维度确定性行为（NO_PROGRESS 停机）= Task 8 `test_feedback_loop.py`。三幕由测试套件集体覆盖；T15（PR-4）将把它们串成 `make demo` 单命令可重复演示。
- **⚠️ testpaths 缺口（延后 PR-5 T16）**：从仓库根裸跑 `pytest` 会收集 `demo/target_repo/tests/*.py`（demo 的 seeded-failure 测试）→ 3 collection errors。修复 = 根 `pyproject.toml` 设 `testpaths=["tests"]`（PLAN Task 16 Step 1 已载明）；CI `unit-test` job 用 `pytest tests/ -q`。非 PR-3 引入，是 demo 仓库的伴生属性。
- **延期 Minor 累计**：PR-2 的 8 项 + PR-3 的 7 项（last_feedback 类型松散、dead `if feedbacks else None`、DENY 冗余 stop=CONTINUE、test_loop/test_integration 未用 import、6 文件缺尾换行、demo 缺陷数 4/3/3 vs brief 近似 5/3/2 已预受）→ 全延后，PR-5 typing-polish/finalize 一并清。

---

## 8. PR-4 收尾（WebUI+演示）合并记录

- **合并方式**：合并入 main 本地（fast-forward，ea31f0e..50d88cc，3 commits）。main 上 `pytest tests/ -q` → 45/45，`python demo/run_demo.py` → ALL ACTS PASS。沿用既定 5-PR 本地策略。
- **§A.6 机制演示项目级满足**：`demo/run_demo.py` 单脚本确定性复现三幕（① 护栏拒 `rm -rf /` ② 反馈闭环 fail→success ③ 无进展停机），全在 MockLLM 下离线运行。`make demo` 单命令接线留 T16。
- **§A.4-C WebUI 隔离**：`src/harness/**` 不 import starlette/uvicorn/webui（grep 零命中）；`src/webui/__init__.py` 空（0 字节）使 `import webui` 不强拖 starlette；测试仅 import `harness.*`，45/45 离线（starlette 未装亦可跑）。WebUI 为纯加性的内核外薄层。
- **§3.6 甲 落地**：SPEC §8 点名「Open Design web skill + Material Design 基线」；`index.html` 实引 `material-components-web@14.0.0` CDN（公开 unpkg，非私有资产）。
- **§5.9 部署就绪**：`make_app(session)->Starlette` 代码级可部署（SSE/approval/static）；公开 URL 部署（Render/Fly.io）为终交付物，明确在 PR-4 范围外，留 PR-5/终交付。
- **延期 Minor 累计**：PR-2(8)+PR-3(7)+PR-4(4)=19 项（server.py dead json import、多文件缺尾换行、make demo/pyproject testpaths 待 T16 接线）→ PR-5 finalize 一并清。

---

## 9. PR-5 收尾（打包+CI）合并记录

- **Task 16（packaging/CLI）**：`pyproject.toml`（PyPI 元数据 + `[tool.pytest.ini_options] testpaths=["tests"]`，**修掉 PR-3 裸 pytest 收集 demo 测试的 gap** + `[tool.ruff]`）+ `Makefile`（test/demo/build/install）+ `cli.py`。CLI 经人工充实为 §3.1 完备（`--init-key`/`--status`/`--update-key`/`--clear-key` + 手写 `.env` loader，无新依赖，`status()` 不回显明文）——brief 原仅 `--init-key`，与 `_safe`/`escape_regex` 同型（spec §3.1 优于 brief）。review clean（§3.1/§3.2/§4.8/§9.2 PASS，make test→45/45，make demo→ALL ACTS PASS）。commit `f3ecfe4`。
- **Task 17（.gitlab-ci.yml）**：`unit-test` job（stage test，`pip install -e .[dev]` → `pytest -q` + `python demo/run_demo.py`）+ `build-wheel` job（stage build，`python -m build` → wheel 制品）。满足 §5.6「必须含名为 unit-test 的 job」+ §3.2 构建步骤。commit `d3f0356`。
- **⚠️ Task 17 评审方式偏离**：SDD 要求每 task 派 sonnet 评审子代理。本轮因会话上下文累积触发 `Request too large (max 32MB)`，Task 17 评审子代理无法正常返回。鉴于此文件仅 15 行 yaml，改为主代理 inline 评审（核对 §5.6 unit-test job 命名/内容、§3.2 build 步骤、CI 用 `pytest -q` 经 testpaths scope 不误收 demo 测试），结论 clean。此偏离已在此记录以保留过程证据；如评分要求严格子代理评审，可在上下文清理后补跑。
- **README.md**：按 §5.4 必含章节撰写（项目简介/安装/运行/分发命令/目录结构/安全边界）+ §3.2（key 安全配置、已知限制）+ §4.11（部署架构 + CI/CD）+ §六（第三方依赖许可证表）。覆盖原 GitLab 占位 README。
- **合并方式**：合并入 main 本地（fast-forward，50d88cc..HEAD）。沿用 5-PR 本地策略。main 上 `pytest -q` → 45/45（testpaths 生效，无须 scope），`python demo/run_demo.py` → ALL ACTS PASS。
- **延期 Minor 终态**：PR-2(8)+PR-3(7)+PR-4(4)=19 项全为 cosmetic/typing-polish（缺尾换行、unused import、dead code、非抽象基类），不影响机制正确性与 §A.4 判据；列为已知技术债，不阻断交付。

---

## 9b. PR-6 收尾（真实 LLM 端到端跑通）合并记录

- **动机**：盲点 2 自承"真实 LLM 从未端到端跑过"——§A.4-C 强项是"移除真实 LLM 仍可单测"（70/70 离线），代价是真实通路从未撞过真实 API/subprocess。本 PR 跑通真实端到端，闭合盲点 2。
- **方式**：主代理 inline 真实跑调试（非 SDD subagent task）。先用 `demo/smoke_provider.py` 冒烟 provider（鉴权+网络+tool_call 解析），再以 `demo/run_live.py` 驱动 `AgentLoop` + `DeepSeekClient` + `ToolDispatcher(workdir=demo/target_repo)` + HITL。每暴露一个 bug 先写红测试再修（TDD）。
- **8 个 mock 不可见 bug**（详见 §3 PR-6 表）：①Windows GBK subprocess 解码崩 ②editable 装主检出致"改了不生效" ③`max-rounds` 不封顶跑 323 轮 ④tool-use 协议没建对致 LLM 300x 读同一文件 ⑤`--json-report-file=-` 写字面文件致 stdout 非 JSON 崩 ⑥validator 对非 JSON stdout 崩 ⑦Windows 绝对路径漏过 guardrail ⑧**run_tests 用控制台脚本致假反馈**（`app.py` 从未加载，LLM 改了没效果——最关键）。
- **关键裁决**：⑧为阻断项。`pytest` 控制台脚本不把 workdir 入 sys.path → 3 collection ImportError；按 pytest 官方推荐改 `python -m pytest`（§2 甲裁决：规范要求优于便利默认）。修后 buggy 报 4 个真实 assertion 失败（带消息），fixed 报 pass/0——反馈闭环终于通。
- **system_prompt 固化**：盲点 4「prompt 措辞定行为」在真实跑复现——LLM 浪费 turn 在 `find`/`dir`/sys.path 调试。强化 prompt：run_tests 优先、repo-relative 路径、禁 exec_shell 调 path。修后 LLM 12 轮内 failures 4→1→0 收敛。
- **结果**：DeepSeek-chat，12 turns，`outcome=success`，rounds=3。failures 单调 4→1→0（反馈闭环驱动收敛）。70/70 单测 + mock 三幕 demo 全绿。**§A.4-A 自编码 main loop 驱动真实 LLM、§A.4-C 机制确定 + 真实通路，双重证据**。
- **合并方式**：合并入 main 本地（fast-forward）。沿用 5-PR 本地策略（第 6 个 PR）。commit `356bd84`（代码）+ 本 docs 提交。

---

## 9c. PR-7 收尾（CLI 真实跑 + 模块级 app + Dockerfile）合并记录

- **动机**：PR-6 闭合盲点 2 后做最终合规矩阵，发现两处代码侧缺口（非 spec 变更）：**G1** `cli.py` 真实 run 是桩（`print("not implemented")`）、`webui/server.py` 无模块级 `app`——而 README 第 78/81 行已文档化 `harness --workdir` 与 `uvicorn webui.server:app`，二者均不工作（README overclaim）。**G2** 无 `Dockerfile`，但 README §分发 写了 `docker build`/`docker run`。PyPI 已满足 §3.2「任选其一」，故 G2 二选一：补 Dockerfile 或删 README docker 段——选前者（容器是 §3.2 明列形态之一，且支撑 §5.9 部署）。
- **G1 实现**：`cli.py` 接真实跑——三模式：`harness --workdir <repo>`（终端 HITL，CliApprover）、`harness --run-webui [--mock]`（浏览器 HITL：bg 线程跑 uvicorn + 主线程跑 AgentLoop，WebApprover 经 session.ask 阻塞等审批）、`harness --headless`（keyless 指向三幕 demo）。`SYSTEM_PROMPT` 提到 `harness/prompt.py`（content物，§A.4-C 不计机制），cli 与 demo 共用不漂移。`_build_loop` 为终端+真实-webui 共享布线点（仅 approver/on_turn 不同），`_build_mock_loop` 复用 run_webui 的脚本（绝对路径触发 guardrail → 浏览器审批卡）。`demo/run_live.py` + `demo/run_webui.py` 转为薄包装（委托 `harness.cli.main`，注入 demo 默认 workdir / `--run-webui`）——真实跑逻辑只在一处，两入口不漂移。`server.py` 加模块级 `app = make_app(WebUISession())`，`uvicorn webui.server:app` 可起。
- **G2 实现**：`Dockerfile`（python:3.11-slim + gcc/make + `pip install -e .[dev,llm]` + EXPOSE 8000），默认 CMD `uvicorn webui.server:app`（§5.9 可达接口）；`make demo` 覆盖为免 token 三幕演示；真实 LLM 跑挂 `-e DEEPSEEK_API_KEY` + `-v broken-repo:/workdir`。`.dockerignore` 排除 `.env`（§3.1：明文 key 绝不进镜像层）。
- **裁决**：不引入 `approve_all_writes`（spec §3.5 扩展，scope creep，已拒）。G1/G2 是补齐 spec 既定 CLI 入口 + README 对齐，非 spec 变更。
- **TDD**：红先——`test_cli.py`（4）：`--headless` 返回 0 且指向 demo.run_demo（keyless）；`_build_loop` 正确注入 client/approver/SYSTEM_PROMPT/6-tool schema（deepseek + anthropic 两种格式）；`_build_mock_loop` 用 WebApprover 且绝对路径触发审批。`test_webui.py`（+1）：模块级 `app` 存在且 `make_app` 仍返回新实例。76 pass（71→76）。
- **真实冒烟**：`harness --run-webui --mock --port 8765` 起服务 → `GET /pending` 见 `{"pending":true,"action":{"tool":"write_file",...}}` → `POST /approve {"approve":true}` → `GET /events` 流式推送 `[turn 1] run_tests verdict=fail failures=1` → `[turn 2] write_file need_approval` → `[turn 3] run_tests verdict=pass failures=0`。CLI 入口 + 模块级 app + HITL 往返 + SSE 全链路打通。
- **结果**：README 不再 overclaim；§3.2 分发（PyPI + 容器）与 §5.9 WebUI 部署代码侧就绪。**合并方式**：本地 ff-merge 入 main（第 7 个 PR）。commit `34003a1`（代码）+ 本 docs 提交。不 push（与最终 REFLECTION 批量）。

---

## 10. 终交付剩余项（学生侧 / 部署侧，非代码）

以下为通用要求 §5 清单中**必须由学生本人或部署动作完成**的项，harness 代码已就绪：

1. **REFLECTION.md（1500–2500 字，§5.8）**：必须学生本人撰写，禁止 AI 代写（§六学术规范）。建议内容见 `通用要求.md` §5 反思报告节（Superpowers 技能发挥/形式大于实质、TDD 在 AI 协作下的角色、subagent-driven 自主运行边界、task 颗粒度、SPEC/PLAN 质量对实现的影响及"规约不清致 subagent 偏离"案例——本项目实例：Task 7 `ModuleNotFoundError` 归类偏差、冷启动 escape_regex/多余 import 两个 PLAN 缺陷、prompt/context 策略、凭据与分发迫使想清的问题、重做会改什么、对 Superpowers 方法论的批判）。
2. ✅ **线上部署 URL + 可访问 WebUI（§5.9）**：已部署于 **Railway**——连 GitHub 镜像仓库 → 读 `Dockerfile` 构建 → web service 注入 `PORT`。公网 URL `https://coding-agent-harness-production.up.railway.app/`（已填入 README）。Dockerfile 默认 CMD 驱动 mock 修复循环（`python -m harness.cli --run-webui --mock`，读 `${PORT:-8000}`），公网实测三幕跑通（审批卡可点 Approve）。不烘焙 LLM key（§3.1）；真实带 key 驱动跑留本地。`render.yaml` 已清理（未用 Render，留 Dockerfile 通用）。
3. ✅ **CI/CD 最后一次 pass（§5.7）**：PR-6 已 push origin（`d749a27..6794a66`），GitLab 流水线通过——`unit-test`（70/70 + demo ALL ACTS PASS）+ `build-wheel`（wheel 制品）均 pass。origin 现与本地 main 同步。
4. **真实 LLM 冒烟（§9.4，可选但推荐）**：✅ 已于 PR-6 跑通（DeepSeek 12 轮 failures 4→0 success，详见 §9b）。`pytest -m live` 标记仍可选补为回归守卫，但真实通路已实证闭合。

---

## 11. 学到的教训（§4.9）

- **PLAN 质量决定 subagent 成败**：冷启动两轮暴露 3 处 PLAN bug（`escape_regex` 误匹配所有含 `/` 路径、Task 8 多余 import、Task 7 fixture 与谓词自相矛盾）。教训——PLAN 里每段代码都须自检「测试预期与此实现是否自洽」，subagent 忠实转写时这些不一致会被原样放大成红色或误判。
- **"遇不确定停下询问"是冷启动的关键规则**：第一轮 agent 自行改 bug（越界 + scope 滚到 10 task），不合规；第二轮强制"停下、引用、两解、不写"，两轮对照证明规则措辞决定 agent 行为。教训——提示词里把"必须停下"写死，比依赖 agent 自觉更可靠。
- **spec 优于 brief 的裁决模式**：`escape_regex`/`_safe`/CLI 三处 brief 偏弱，均以 SPEC 字面要求为准硬化（甲）。教训——当 brief 与 spec 冲突时，裁决依据应是 spec，并在 AGENT_LOG 记录该偏离与理由（过程证据）。
- **mock-LLM 抽象层是 §A.4-C 的地基**：`LLMClient` 协议 + `MockLLMClient` + `AutoRejectApprover` + `FakeKeyring` 让 77/77 测试全程离线、确定性、无网络/keyring/subprocess。教训——先定抽象接口再写实现，mock 与真实共用契约，机制可测性在第一行代码就锁定。
- **工作树 cwd 钉住风险**：PR-1 收尾时 `git worktree remove` 因会话 cwd 钉在该路径失败并清空内部文件。教训——harness 钉住的 cwd 不能中途 `worktree remove`；改用"同一 pinned 路径上切换分支"复用工作树，把持久账本（`progress.md`）放主树而非工作树内。
- **plan-mandated 发现属人工裁决域**：Task 9 `_safe` startswith 是 brief 指定的形式，子代理照抄后评审标为 plan-mandated Important——这类不归子代理修，须人工在 SPEC/PLAN 层裁决。教训——SDD 评审要区分"实现 bug"与"规约 bug"，后者上交人工。
- **mock 不可见的 bug 只有真实跑暴露**（PR-6）：70/70 离线单测全绿 ≠ 真实通路可用。真实跑一遍暴露 8 个 mock 永不触发的 bug——Windows GBK 解码、tool-use 协议缺失、`python -m pytest` vs 控制台脚本的 sys.path 差异、`--json-report-file=-` 的字面文件行为。教训——§A.4-C「移除真实 LLM 仍可单测」是强项，但**必须**配一次真实端到端冒烟，否则 mock 给出虚假信心。盲点 2 由此闭合。
- **反馈必须是真反馈**（PR-6 #8）：harness 长期报"3 failures"实为 3 个 collection ImportError——`app.py` 从未加载，LLM 怎么改都不变，看似"LLM 不行"实为 harness 喂假反馈。LLM 反复查 sys.path 是**正确**响应（它看到了 `ModuleNotFoundError`），从源码内部却改不了。教训——当 agent 反复在某一非源码维度打转时，先怀疑反馈本身的真实性，而非 agent 能力。
- **上下文体积是硬约束**：Task 17 评审因子代理触发 32MB 上限无法返回。教训——长 SDD 链中，对体量小的收尾 task，inline 评审是合理回退，但须在 AGENT_LOG 记录偏离以保留过程证据；定期 `/compact` 与及时合并入 main 可缓解。
- **默认值不能有两份**（PR-7 收尾复核）：`config.py` 的 `GuardrailRules.escape_regex` dataclass 默认是硬化版（含 Windows 盘符+UNC，PR-6 #7 修），但 `Config.load()` 的 `g.get("escape_regex", ...)` fallback 抄了一份**弱版**（仅 POSIX `^/`+`..`）。config.yaml 碰巧带硬化值所以线上没炸，但任何缺该键的自定义 yaml 会静默退回 guardrail 漏洞。教训——同一默认值出现两处必漂移；dataclass 默认与 loader fallback 必须引用同一常量（单源真相），并配一条「缺键时 fallback == dataclass 默认」的回归测试钉住。
