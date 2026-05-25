# Book Agent MVP

AI Book-Writing Agent 的本地 MVP，实现“创建项目 → 生成章节 → 审计 → 追踪表更新 → 快照 → 恢复”的最小闭环。

当前版本不依赖外部 Python 包；LLM Provider 暂时是可替换的 mock 实现，用于先验证工程状态流。真实 OpenAI/Claude Provider、异步任务队列、长跨度对齐和高级导出会在后续迭代中接入。

## 当前能力

- 创建小说项目，支持推理、科幻、玄幻三种题材。
- 生成单章或连续生成 3 章 demo。
- 每章生成后运行通用审计和题材审计。
- 自动更新题材追踪表。
- 生成 pass/warning/fail 审计报告。
- 每章保存滚动快照，并支持从快照恢复。
- 本地 GUI 查看章节、审计报告、追踪表、快照。
- 导出草稿 Markdown、审计 JSON、追踪表 JSON、项目快照 JSON。

## 目录结构

```text
book_agent/
  models.py          # 领域模型
  services.py        # 核心服务：创建、生成、审计、快照、导出
  strategies.py      # 推理/科幻/玄幻题材策略和追踪表定义
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

## 使用方法

1. 打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。
2. 在左侧填写书名、题材、篇幅和核心创意。
3. 点击“创建”。
4. 点击“生成一章”或“生成三章”。
5. 在右侧查看章节、最新审计、追踪表和快照。
6. 使用导出按钮下载草稿或状态数据。

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

## 测试

```powershell
pytest -q
```

当前测试覆盖：

- 创建项目并连续生成 3 章。
- 审计报告和追踪表更新。
- 追踪表补丁幂等。
- 快照恢复。
- 导出草稿和追踪表。

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

## 下一步重点

- 接入真实 LLM Provider。
- 将当前同步本地任务队列升级为可暂停/取消/重试的持久化任务队列。
- 增强自动修订和人工处理队列。
- 增加 `.docx` / `.pdf` 导出。
- 实现长跨度对齐、全局扫描和 VolumeBridge。
