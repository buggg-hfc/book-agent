# Book Agent MVP

AI Book-Writing Agent 的本地 MVP，实现"创建项目 → 生成章节 → 审计 → 追踪表更新 → 快照 → 恢复"的最小闭环。

后端不依赖外部 Python 包；默认对接 OpenAI-compatible LLM（未配置 API key 时自动回退到 mock 并打印警告）。GUI 为 React + Vite 工作台，生产构建产物由 Python 服务直接托管。

## 当前能力

- 创建小说项目，支持推理、科幻、玄幻三种题材；创建时自动保存初始永久快照。
- 生成单章或连续生成示例三章。章节生成为异步任务，前端通过 SSE 实时显示步骤进度、token 数和耗时。
- 每章生成后运行通用审计和题材审计，自动更新题材追踪表，生成 pass/warning/fail 审计报告。
- 项目支持查看信息和一键删除（同步清理关联快照文件）。
- 每章保存滚动快照，并支持从快照恢复；支持手动、情节弧、分卷、紧急快照。
- 本地 GUI 提供三步创建向导、主流程按钮、章节阅读、审计、追踪表、快照和导出页。
- 高级 GUI 区提供任务状态（含 token/耗时）、全局扫描、VolumeBridge、快照管理和 LLM 配置查看。
- 支持恢复前差异摘要、四层恢复上下文和恢复风格验证。
- 支持手动编辑 dirty range、摘要链/向量索引/追踪表/审计重建。
- 支持长跨度对齐、全局扫描和 VolumeBridge 生成/确认。
- 支持任务暂停、继续、取消、重试和同项目写任务互斥锁。
- LLM 输出自动去除 `<think>` 思考标签；API 调用默认绕过系统代理。
- 导出草稿 Markdown、审计 JSON、追踪表 JSON、项目快照 JSON、VolumeBridge JSON、DOCX、PDF。

## 目录结构

```text
book_agent/
  models.py          # 领域模型（含 JobEvent、WritingJob）
  services.py        # 核心服务：创建、生成、审计、快照、导出；JobManager（事件队列+线程池）
  strategies.py      # 推理/科幻/玄幻题材策略和追踪表定义
  providers.py       # MockLLMProvider + OpenAI-compatible 流式 Provider
  memory.py          # 风格锚定、摘要链、长跨度对齐、VolumeBridge
  storage.py         # JSON 持久化
  server.py          # 标准库 HTTP 服务（含 SSE 端点）
frontend/
  src/               # React + Vite GUI 源码
  package.json       # 前端依赖与构建脚本
static/
  index.html         # 前端生产构建入口
  assets/            # Vite 构建产物
tests/
  test_mvp_flow.py   # MVP 流程测试
book-agent-development-plan.md   # 架构与题材策略详细设计文档
```

## 环境要求

- Python 3.11+
- Node.js 20+（仅开发或重新构建 GUI 时需要）
- Windows PowerShell、macOS Terminal 或 Linux shell

`pyproject.toml` 没有运行时依赖；测试需要 `pytest`：

```bash
python -m pip install pytest
```

前端依赖安装：

```bash
cd frontend && npm install
```

## 启动

在项目根目录运行：

```bash
python -m book_agent.server
```

默认地址：[http://127.0.0.1:8000](http://127.0.0.1:8000)

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

## 配置

所有配置均可通过环境变量覆盖：

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `BOOK_AGENT_DATA_DIR` | `data` | 本地 JSON 数据目录 |
| `BOOK_AGENT_CHECKPOINT_DIR` | `data/checkpoints` | 快照目录 |
| `BOOK_AGENT_WARNING_THRESHOLD` | `1` | 审计 warning 阈值 |
| `BOOK_AGENT_CHECKPOINT_KEEP_RECENT` | `5` | 章节滚动快照保留数量 |
| `BOOK_AGENT_LLM_PROVIDER` | `openai_compatible` | `mock`、`openai` 或 `openai_compatible` |
| `BOOK_AGENT_LLM_API_KEY` / `OPENAI_API_KEY` | — | 真实 Provider API key |
| `BOOK_AGENT_LLM_BASE_URL` / `OPENAI_BASE_URL` | — | OpenAI-compatible chat completions URL |
| `BOOK_AGENT_LLM_MODEL` / `OPENAI_MODEL` | — | 模型名 |
| `BOOK_AGENT_LLM_SYSTEM_PROMPT` | — | 默认 system prompt |
| `BOOK_AGENT_LLM_TEMPERATURE` | `0.4` | 默认温度 |
| `BOOK_AGENT_LLM_MAX_TOKENS` | — | 默认最大输出 token，可留空 |
| `BOOK_AGENT_LLM_MAX_RETRIES` | `2` | LLM 调用失败重试次数 |
| `BOOK_AGENT_LLM_NO_PROXY` | `false` | `true` 时绕过系统 HTTP 代理（默认已绕过） |
| `BOOK_AGENT_LLM_PROMPT_TOKEN_COST` | `0.0` | 每 1K 输入 token 成本估算 |
| `BOOK_AGENT_LLM_COMPLETION_TOKEN_COST` | `0.0` | 每 1K 输出 token 成本估算 |
| `BOOK_AGENT_JOB_TIMEOUT_SECONDS` | `120` | 后台任务超时时间 |

未配置 API key 时 provider 自动回退到 mock，并在控制台打印 `RuntimeWarning`。

## 使用方法

1. 打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。
2. 点击"创建新项目"，按三步向导填写基础信息、写作目标并确认。
3. 点击"生成第一章"或"继续生成"；进度条实时显示生成步骤和 token 数。
4. 在标签页中查看章节稿件、审计、追踪表、快照和导出。
5. 侧边栏项目卡悬停时出现删除按钮，支持一键删除项目及所有关联数据。
6. 任务管理、全局扫描、VolumeBridge 和 LLM 配置在"高级工具"标签页中。

## 常用 API

### 项目管理

```bash
# 创建项目
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"title":"镜中之罪","theme":"mystery","scale":"medium","core_idea":"一个密室案件"}'

# 列出项目
curl http://127.0.0.1:8000/api/projects

# 删除项目
curl -X DELETE http://127.0.0.1:8000/api/projects/<project_id>
```

### 章节生成（异步 + SSE）

```bash
# 启动生成任务（立即返回 job_id）
curl -X POST http://127.0.0.1:8000/api/projects/<project_id>/chapters/generate

# 订阅生成进度（SSE 流）
curl http://127.0.0.1:8000/api/jobs/<job_id>/stream

# 连续生成示例三章
curl -X POST "http://127.0.0.1:8000/api/projects/<project_id>/chapters/demo?count=3"
```

### 导出

```bash
curl http://127.0.0.1:8000/api/projects/<project_id>/export/manuscript_md
```

支持的导出类型：`manuscript_md`、`audit_json`、`tracking_json`、`snapshot_json`、`volume_bridge_json`、`docx`、`pdf`

### LLM 配置

```bash
# 查看当前配置
curl http://127.0.0.1:8000/api/llm/config

# 热重载 LLM 配置（修改环境变量后无需重启）
curl -X POST http://127.0.0.1:8000/api/llm/reload

# 直接调用文本生成
curl -X POST http://127.0.0.1:8000/api/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"生成一句宣传语","system_prompt":"只输出一句中文","temperature":0.3,"max_tokens":80}'
```

### 其他操作

```bash
# 全局扫描
curl http://127.0.0.1:8000/api/projects/<project_id>/scan

# 长跨度对齐
curl "http://127.0.0.1:8000/api/projects/<project_id>/align?q=主角%20线索"

# 生成 VolumeBridge
curl -X POST http://127.0.0.1:8000/api/projects/<project_id>/volume_bridge
```

## 测试

```bash
pytest -q
```

前端类型检查和生产构建：

```bash
cd frontend
npm run typecheck
npm run build
```

当前测试覆盖：

- 创建项目并连续生成 3 章（含初始快照验证）。
- 审计报告和追踪表更新、补丁幂等。
- 快照恢复、恢复差异、恢复验证。
- 事件日志重放和 dirty range 重建。
- 后台任务暂停、继续、取消、重试和写锁。
- 参数建议、结构化输出校验和枚举校验。
- 后端 LLM 配置查询、直接文本调用、结构化调用和调用记录。
- 全局扫描、长跨度对齐和 VolumeBridge。
- Markdown、JSON、DOCX、PDF 导出。

## 本地数据

运行数据保存在 `data/`（已被 `.gitignore` 忽略）。删除 `data/` 可以清空本地项目和快照。

## 开发约定

- 架构与题材策略详细设计见 [book-agent-development-plan.md](book-agent-development-plan.md)。
- 新增功能、启动方式、测试方式、API 或数据目录变化时，同步更新本 README。

## 当前边界

- 未配置 API key 时自动回退 mock Provider，适合本地流程验证；接入真实模型只需设置 `BOOK_AGENT_LLM_API_KEY` 和 `BOOK_AGENT_LLM_BASE_URL`。
- 本地任务队列是进程内实现，适合 MVP 和单机验证；生产化部署应替换为持久化队列。
- 向量检索为词频向量 MVP，用于验证三路对齐流程；生产化可接入专业向量库。
