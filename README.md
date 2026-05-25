# Book Agent MVP

AI Book-Writing Agent 的本地 MVP，实现“创建项目 → 生成章节 → 审计 → 追踪表更新 → 快照 → 恢复”的最小闭环。

当前版本不依赖外部 Python 包；默认使用 mock LLM Provider，也可以通过 OpenAI-compatible HTTP 接口接入真实模型。MVP 已覆盖章节生成、审计、快照恢复、事件重放、长跨度对齐、VolumeBridge 和多格式导出。

## 当前能力

- 创建小说项目，支持推理、科幻、玄幻三种题材。
- 生成单章或连续生成 3 章 demo。
- 每章生成后运行通用审计和题材审计。
- 自动更新题材追踪表。
- 生成 pass/warning/fail 审计报告。
- 每章保存滚动快照，并支持从快照恢复。
- 本地 GUI 查看章节、审计报告、追踪表、快照。
- 支持手动、弧、卷、应急快照；章节快照滚动保留，里程碑快照永久保留。
- 支持恢复前差异摘要、四层恢复上下文和恢复风格验证。
- 支持手动编辑 dirty range、摘要链/向量索引/追踪表/审计重建。
- 支持长跨度对齐、全局扫描和 VolumeBridge 生成/确认。
- 支持任务暂停、继续、取消、重试和同项目写任务互斥锁。
- 导出草稿 Markdown、审计 JSON、追踪表 JSON、项目快照 JSON、VolumeBridge JSON、DOCX、PDF。

## 目录结构

```text
book_agent/
  models.py          # 领域模型
  services.py        # 核心服务：创建、生成、审计、快照、导出
  strategies.py      # 推理/科幻/玄幻题材策略和追踪表定义
  providers.py       # mock 与 OpenAI-compatible LLM Provider
  memory.py          # 风格锚定、摘要链、长跨度对齐、VolumeBridge
  storage.py         # JSON 持久化
  server.py          # 标准库 HTTP 服务
static/
  index.html         # 本地 GUI
tests/
  test_mvp_flow.py   # MVP 流程测试
book-agent-development-plan.md
book-agent-engineering-todo.md
```

## 环境要求

- Python 3.11+
- Windows PowerShell、macOS Terminal 或 Linux shell

当前 `pyproject.toml` 没有运行时依赖；测试需要 `pytest`。如果本机没有 pytest：

```powershell
python -m pip install pytest
```

## 启动

在项目根目录运行：

```powershell
python -m book_agent.server
```

默认地址：

[http://127.0.0.1:8000](http://127.0.0.1:8000)

健康检查：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
```

也可以使用脚本：

```powershell
.\scripts\start.ps1 -Port 8000
```

## 配置

所有配置都可以通过环境变量覆盖：

- `BOOK_AGENT_DATA_DIR`：本地 JSON 数据目录，默认 `data`。
- `BOOK_AGENT_DATABASE_URL`：数据库逻辑地址，默认 `json://data/projects`。
- `BOOK_AGENT_VECTOR_STORE_PATH`：本地向量索引目录，默认 `data/vector_index`。
- `BOOK_AGENT_CHECKPOINT_DIR`：快照目录，默认 `data/checkpoints`。
- `BOOK_AGENT_WARNING_THRESHOLD` / `BOOK_AGENT_FAIL_THRESHOLD`：审计阈值。
- `BOOK_AGENT_CHECKPOINT_KEEP_RECENT`：章节滚动快照保留数量。
- `BOOK_AGENT_QUEUE_MAX_WORKERS` / `BOOK_AGENT_QUEUE_POLL_INTERVAL_MS`：本地任务队列参数。
- `BOOK_AGENT_LLM_PROVIDER`：`mock`、`openai` 或 `openai_compatible`。
- `BOOK_AGENT_LLM_API_KEY` / `OPENAI_API_KEY`：真实 Provider API key，接口不会返回该值。
- `BOOK_AGENT_LLM_BASE_URL` / `OPENAI_BASE_URL`：OpenAI-compatible chat completions URL。
- `BOOK_AGENT_LLM_MODEL` / `OPENAI_MODEL`：模型名。
- `BOOK_AGENT_LLM_SYSTEM_PROMPT`：默认 system prompt。
- `BOOK_AGENT_LLM_TEMPERATURE`：默认温度，默认 `0.4`。
- `BOOK_AGENT_LLM_MAX_TOKENS`：默认最大输出 token，可留空。
- `BOOK_AGENT_LLM_MAX_RETRIES`：LLM 调用失败重试次数，默认 `2`。
- `BOOK_AGENT_LLM_PROMPT_TOKEN_COST` / `BOOK_AGENT_LLM_COMPLETION_TOKEN_COST`：每 1K token 成本估算。

## 使用方法

1. 打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。
2. 在左侧填写书名、题材、篇幅和核心创意。
3. 点击“创建”。
4. 点击“生成一章”或“生成三章”。
5. 在右侧查看章节、最新审计、追踪表和快照。
6. 需要时执行修订、接受警告、人工处理、全局扫描、快照恢复或 VolumeBridge 确认。
7. 使用导出按钮下载草稿或状态数据。

## 常用 API

创建项目：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/projects" `
  -ContentType "application/json" `
  -Body '{"title":"镜中之罪","theme":"mystery","scale":"medium","core_idea":"一个密室案件"}'
```

生成一章：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/projects/<project_id>/chapters/generate"
```

生成三章 demo：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/projects/<project_id>/chapters/demo?count=3"
```

导出草稿：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/<project_id>/export/manuscript_md"
```

支持的导出类型：

- `manuscript_md`
- `audit_json`
- `tracking_json`
- `snapshot_json`
- `volume_bridge_json`
- `docx`
- `pdf`

生成 VolumeBridge：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/projects/<project_id>/volume_bridge"
```

全局扫描：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/<project_id>/scan"
```

长跨度对齐：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/projects/<project_id>/align?q=主角%20线索"
```

查看 LLM 配置：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/llm/config"
```

直接调用文本生成：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/llm/generate" `
  -ContentType "application/json" `
  -Body '{"prompt":"为这本书生成一句宣传语","system_prompt":"只输出一句中文","temperature":0.3,"max_tokens":80}'
```

直接调用结构化输出：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/llm/structured" `
  -ContentType "application/json" `
  -Body '{"prompt":"输出审计状态 JSON","schema":{"required":["summary"],"defaults":{"summary":"ok"},"enums":{"status":["pass","warning","fail"]}}}'
```

环境变量变更后重新加载 LLM 配置：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/llm/reload"
```

## 测试

```powershell
pytest -q
```

当前测试覆盖：

- 创建项目并连续生成 3 章。
- 审计报告和追踪表更新。
- 追踪表补丁幂等。
- 快照恢复、恢复差异、恢复验证。
- 事件日志重放和 dirty range 重建。
- 后台任务暂停、继续、取消、重试和写锁。
- 参数建议、结构化输出校验。
- 后端 LLM 配置查询、直接文本调用、结构化调用和调用记录。
- 全局扫描、长跨度对齐和 VolumeBridge。
- Markdown、JSON、DOCX、PDF 导出。

## 本地数据

运行数据保存在：

```text
data/
```

该目录已被 `.gitignore` 忽略。删除 `data/` 可以清空本地项目和快照。

## 开发约定

- 开发计划见 [book-agent-development-plan.md](book-agent-development-plan.md)。
- 工程进度见 [book-agent-engineering-todo.md](book-agent-engineering-todo.md)。
- 每次新增功能、启动方式、测试方式、API 或数据目录变化时，都要同步更新本 README。
- 每次完成或部分完成 TODO，都要更新 `book-agent-engineering-todo.md` 的勾选状态。

## 当前边界

- 默认 mock Provider 适合本地流程验证；真实模型需要配置 OpenAI-compatible 环境变量。
- 本地任务队列是进程内实现，适合 MVP 和单机验证；生产化部署应替换为持久化队列。
- 向量检索为词频向量 MVP，用于验证三路对齐流程；生产化可接入专业向量库。
