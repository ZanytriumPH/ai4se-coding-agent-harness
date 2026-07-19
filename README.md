# Coding Agent Harness

> *Spec-Driven, Subagent-Built, Human-Owned.* — 一台自编码的编码智能体外壳（Coding Agent Harness）。

给定一个带有失败测试 / lint / 类型错误的小型 Python 仓库，本 harness 能自主读代码、改代码、跑校验、据**客观结构化反馈**多轮自我修正，在危险动作前停下等人工审批，并跨会话记住项目约定与失败教训。

本项目为 AI4SE 期末项目 A。核心纪律：harness 内核（主循环、工具、治理、反馈、记忆）**全部自编码**，可注入 mock LLM 走确定性单测；**未寄生**在 LangChain / AutoGen / CrewAI 等高层 agent loop 之上。

---

## 项目简介

`Agent = LLM + Harness`。当 LLM 能完成大部分编码思考时，工程师的真正价值落在 harness 这层工程：治理、反馈、上下文、安全、分发。本项目把这层亲手编码并批判性理解。

- **反馈闭环（重点维度）**：解析 pytest / ruff / mypy 结构化产物 → 客观判定 pass/fail + 失败分类（封闭枚举）→ 结构化摘要回灌上下文 → 驱动 agent 多轮修正 → 停机判断（成功 / 无进展 / 轮次超限）。
- **治理护栏**：声明式规则识别危险动作（越界文件、改 CI/凭据文件、curl/wget、git push、rm -rf 等）→ Allow / Deny / NeedApproval；人工审批走 `Approver` 接口（CLI / Web / AutoReject 三实现）。
- **记忆**：JSON Lines + 标签检索，自实现（不接向量库 / 框架 memory）。
- **WebUI**：Starlette SSE 流式推送每轮步骤 + 审批回传，为内核外薄层（不参与 mock 单测路径）。

机制演示三幕（mock LLM 下确定性复现，`make demo`）：① 护栏拦截 `rm -rf /`；② 注入失败 → 反馈回灌 → agent 改变下一步 → 成功；③ 无进展停机。

---

## 安装

要求：Python ≥ 3.11，Windows / macOS / Linux 均可。

```bash
git clone <repo-url> coding-agent-harness
cd coding-agent-harness
pip install -e .[dev]          # 内核 + 测试依赖
# 可选真实 LLM 运行：
pip install -e .[dev,llm]      # 追加 anthropic SDK
# 若用 DeepSeek（OpenAI 兼容协议，仅需 httpx，已在内核依赖中）
```

开发依赖：`pytest`、`ruff`、`mypy`、`pytest-json-report`（见 `pyproject.toml`）。

---

## 运行

### 一键测试与演示

```bash
make test     # pytest -q（45 个离线单测，全程无网络 / 无真实 LLM）
make demo     # python demo/run_demo.py（§A.6 三幕机制演示，ALL ACTS PASS）
make build    # python -m build（产出 wheel 到 dist/）
make install  # pip install -e .[dev,llm]
```

### 凭据安全配置（首次必读）

凭据（LLM API key）存储遵循「三不」：**不硬编码、不入 git、不入日志**。主存储为操作系统钥匙串（`keyring` → Windows Credential Manager / macOS Keychain / Linux Secret Service），`.env` 仅作备选来源并标注明文风险。

```bash
python -m harness.cli --init-key      # 首次引导录入（隐藏输入，不回显明文）
python -m harness.cli --status        # 查看状态：configured / not configured（绝不回显明文）
python -m harness.cli --update-key     # 更新 key（覆盖旧值）
python -m harness.cli --clear-key      # 清除 key 后打印状态
```

`.env` 备选来源（明文风险：进程环境可见、文件明文，仅当系统钥匙串不可用时使用）：

```
# .env（已被 .gitignore 排除，切勿提交）
DEEPSEEK_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### 运行 harness

```bash
# Headless mock 演示（无 key，确定性）——CLI 指向三幕机制演示
python -m harness.cli --headless
python -m demo.run_demo              # 等价：直接跑三幕演示

# 真实 LLM 修复任务（需先 --init-key）
harness --config config.yaml --workdir <target-repo>
python -m demo.run_live               # 等价：workdir 默认 demo/target_repo

# WebUI（浏览器 HITL，本地或部署）——服务前端 + 驱动 AgentLoop
harness --run-webui --workdir <target-repo>          # 真实 LLM
harness --run-webui --mock                           # 免 token 脚本演示（触发 1 次审批）
python -m demo.run_webui --mock                       # 等价：workdir 默认 demo/target_repo

# 仅服务 WebUI 前端（不驱动循环，部署态/反代用）
uvicorn webui.server:app --host 0.0.0.0 --port 8000
```

### 真实 LLM 冒烟（可选）

带 `@pytest.mark.live` 标记，CI 默认 skip，需 key：

```bash
pytest -m live -q
```

---

## 分发命令

分发形态：**PyPI 包 + 原生运行**（主）；可选 Docker 镜像作演示。

```bash
# 构建 wheel
python -m build                  # → dist/coding_agent_harness-*.whl

# 安装分发产物
pip install dist/coding_agent_harness-*.whl

# （可选）Docker —— 单条 build + 单条 run 即可启动（§3.2 容器形态）
docker build -t coding-agent-harness .

# 默认 CMD 服务 WebUI 前端于 :8000（§5.9 可访问接口）
docker run --rm -p 8000:8000 coding-agent-harness

# 免 token 三幕机制演示（终端）
docker run --rm -it coding-agent-harness make demo

# 真实 LLM 浏览器 HITL：挂载待修仓库 + 注入 key（env 为明文，进程可见；生产态优先宿主 keyring）
docker run --rm -p 8000:8000 \
    -e DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY \
    -v /path/to/broken-repo:/workdir \
    coding-agent-harness harness --run-webui --host 0.0.0.0 --workdir /workdir
```

CI（`.gitlab-ci.yml`）含 `build-wheel` job，每次合并自动产出 wheel 制品。

---

## 目录结构

```
.
├── SPEC.md / PLAN.md / SPEC_PROCESS.md / AGENT_LOG.md   # 规约 / 计划 / 过程 / 日志
├── README.md / REFLECTION.md                            # 本文件 / 学生反思（本人撰写）
├── config.yaml                          # 声明式规则（guardrail / validator 阈值 / provider）
├── pyproject.toml / Makefile / .gitlab-ci.yml          # 打包 / 任务 / CI
├── src/
│   ├── harness/                         # ★ harness 内核（自编码，可 mock 单测）
│   │   ├── models.py                    #   数据模型 + 失败指纹
│   │   ├── config.py                    #   声明式配置加载
│   │   ├── loop.py                      #   AgentLoop 主循环（§A.4-A 核心）
│   │   ├── credentials.py               #   CredentialStore（keyring + .env loader）
│   │   ├── cli.py                       #   CLI 入口
│   │   ├── llm/                         #   LLMClient 协议 + Mock/DeepSeek/Anthropic
│   │   ├── governance/                  #   Guardrail + Approver（CLI/Web/AutoReject）
│   │   ├── feedback/                    #   Validators + FeedbackLoop（★ 重点维度）
│   │   ├── memory/                      #   JSON Lines + 标签检索（自实现）
│   │   └── tools/                       #   ToolDispatcher + read/write/shell/runner 工具
│   └── webui/                           # 内核外薄层（SSE + 审批，Open Design / Material CDN）
├── tests/                               # 45 个离线单测 + fixtures
└── demo/
    ├── run_demo.py                      # §A.6 三幕机制演示
    └── target_repo/                     # 手写 mini 目标仓库（§六 标注，含 seeded 失败）
```

---

## 安全边界说明

1. **凭据**：见上文「凭据安全配置」。`status()` 仅回 `configured` / `not configured`，绝不回显明文；测试用 `FakeKeyring` 注入，不碰真实 OS 钥匙串、不依赖网络。
2. **路径围栏**：harness 仅在工作目录内写文件；`_safe` 守卫用 `base in target.parents` 拒绝兄弟前缀绕过与目录逃逸（`../`、绝对路径 `/etc/...`）。Windows 沙箱缺失，以 guardrail 规则围栏替代——已知设计取舍。
3. **危险动作治理**：`config.yaml` 声明式规则——
   - 越界文件操作（绝对路径 / `..` 逃逸）→ `NeedApproval`
   - CI / 凭据文件（`.github/`、`.gitlab-ci.yml`、`.env`）→ 绝对 `Deny`
   - 网络：白名单放行包管理器（`pip install`、`npm install`），黑名单拦 `curl` / `wget` / `iptables`
   - git：`commit` 放行，`push` 死拦
   - 破坏性 shell：黑名单正则（`rm -rf` / `sudo` / `chmod 777` / `mkfs` / `DROP` / `TRUNCATE`）
4. **HITL 审批**：CLI 终端 `y/N`；WebUI 弹窗；测试态 `AutoRejectApprover` 零 I/O 注入，确定性单测。

---

## 部署架构与 CI/CD

- **CI/CD**：`.gitlab-ci.yml`，两阶段：
  - `unit-test`（stage: test）：`pip install -e .[dev]` → `pytest -q` + `python demo/run_demo.py`。每次 push 自动运行。
  - `build-wheel`（stage: build）：`python -m build` → wheel 制品。
  - 要求：最后一次 CI 执行必须为 pass 状态。
- **WebUI 部署（§5.9）**：公开 URL 见仓库 `Settings → Pages` 或 README 顶部更新。架构：`uvicorn` 跑 Starlette `webui.server:app`，前端 Material Components Web CSS（CDN 引入），SSE `/events` 流式推送步骤、`POST /approve` 回传审批。

---

## 第三方依赖与许可证

| 依赖 | 用途 | 许可证 |
|---|---|---|
| httpx | LLM provider HTTP 客户端（DeepSeek / Anthropic） | BSD-3-Clause |
| PyYAML | 声明式配置加载 | MIT |
| keyring | OS 钥匙串凭据存储 | MIT |
| starlette | WebUI SSE + 审批路由 | BSD-3-Clause |
| uvicorn | ASGI server | BSD-3-Clause |
| pytest / ruff / mypy | 测试 / lint / 类型（开发依赖） | MIT / MIT / MIT |
| anthropic | Anthropic SDK（可选 `[llm]`） | MIT |
| Material Components Web | 前端设计系统基线（CDN 引入，§3.6） | Apache-2.0 |

---

## 已知限制

- **平台**：Windows / macOS / Linux 均支持；Windows 下无 OS 沙箱，以 guardrail 规则围栏替代。
- **架构**：单进程同步 loop（非 worker 队列）；适合单任务修复，非高并发场景。
- **依赖前提**：Python ≥ 3.11；真实 LLM 运行需自备 DeepSeek 或 Anthropic key。
- **国产 LLM 工具调用稳定性**：DeepSeek 偶发不遵从 function-calling 格式 → `LLMClient` 层 robust 解析 + 失败重试；单测不依赖此（用 MockLLM）。
- **无进展检测**：失败指纹不含 message 文本（避免误判），极端情况仍可能误判——已知限制。

---

## 文档导航

- `SPEC.md` — 设计文档（领域与机制设计、凭据威胁模型、机制演示映射、验收标准）
- `PLAN.md` — 实现计划（18 task、5 PR、worktree/PR 划分）
- `SPEC_PROCESS.md` — brainstorming 过程 + 冷启动验证客观证据
- `AGENT_LOG.md` — 开发过程日志（技能触发、子代理提交、人工裁决）
- `REFLECTION.md` — 学生本人反思报告（1500–2500 字，本人撰写）
