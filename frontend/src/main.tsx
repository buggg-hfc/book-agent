import React from "react";
import ReactDOM from "react-dom/client";
import {
  AlertTriangle,
  Archive,
  BookOpen,
  Bot,
  Check,
  ChevronRight,
  ClipboardCheck,
  Database,
  Download,
  Eye,
  EyeOff,
  FileText,
  Gauge,
  History,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  Table2,
  Trash2,
  Wand2,
  XCircle
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import "./styles.css";

type Status = "pass" | "warning" | "fail" | string;

type ProjectSummary = {
  id: string;
  title: string;
  theme: string;
  scale: string;
  chapter_count: number;
  checkpoint_count: number;
  latest_status: Status | null;
  created_at: string;
  updated_at: string;
};

type LlmCallRecord = {
  provider: string;
  model: string;
  prompt_tokens_estimate: number;
  output_tokens_estimate: number;
  cost_estimate: number;
  latency_ms: number;
  retry_count: number;
};

type JobEvent = {
  job_id: string;
  event_type: string;
  step: string;
  progress: number;
  detail: string | null;
  llm_record: LlmCallRecord | null;
  stream_tokens_out: number;
};

type Chapter = {
  id: string;
  chapter_no: number;
  title: string;
  text: string;
  outline_summary: string;
  created_at: string;
};

type AuditFinding = {
  id: string;
  scope: string;
  table_name: string | null;
  rule: string;
  status: Status;
  detail: string;
  suggested_fix?: string | null;
  blocking?: boolean;
};

type AuditReport = {
  id: string;
  chapter_no: number;
  findings: AuditFinding[];
  score: number;
  overall_status: Status;
  decision: string;
  warning_count: number;
  fail_count: number;
};

type Checkpoint = {
  id: string;
  type: string;
  chapter_no: number | null;
  created_at: string;
  retention_policy: string;
};

type WritingJob = {
  id: string;
  type: string;
  status: string;
  progress: number;
  current_step: string;
  error?: string | null;
  retry_count: number;
  last_llm_record?: LlmCallRecord | null;
};

type Project = {
  id: string;
  meta: Record<string, string>;
  creation_params: Record<string, unknown>;
  chapters: Chapter[];
  audit_reports: AuditReport[];
  theme_tracking_tables: Record<string, Array<Record<string, unknown>>>;
  checkpoints: Checkpoint[];
  volume_bridges?: Array<Record<string, unknown>>;
  updated_at: string;
};

type LlmConfig = {
  provider: string;
  configured_provider: string;
  model: string;
  api_key_configured: boolean;
  temperature: number;
  max_tokens: number | null;
  timeout_seconds: number;
};

type AppSettings = {
  llm_provider: string;
  openai_api_key: string;
  openai_api_key_set: boolean;
  openai_base_url: string;
  openai_model: string;
  llm_system_prompt: string;
  llm_temperature: number;
  llm_max_tokens: number | null;
  llm_max_retries: number;
  llm_prompt_token_cost: number;
  llm_completion_token_cost: number;
  llm_no_proxy: boolean;
  _saved_fields: string[];
};

type Toast = { tone: "success" | "warning" | "danger"; text: string };
type TabKey = "manuscript" | "audit" | "tracking" | "snapshots" | "export" | "advanced";

const themeLabels: Record<string, string> = {
  mystery: "推理",
  sci_fi: "科幻",
  xuanhuan: "玄幻"
};

const scaleLabels: Record<string, string> = {
  micro: "微型",
  short: "短篇",
  medium: "中篇",
  long: "长篇",
  epic: "超长篇"
};

const tabs: Array<{ key: TabKey; label: string; icon: LucideIcon }> = [
  { key: "manuscript", label: "章节稿件", icon: BookOpen },
  { key: "audit", label: "审计", icon: ClipboardCheck },
  { key: "tracking", label: "追踪表", icon: Table2 },
  { key: "snapshots", label: "快照", icon: History },
  { key: "export", label: "导出", icon: Download },
  { key: "advanced", label: "高级工具", icon: Settings }
];

const api = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || response.statusText);
  }
  return data as T;
};

function App() {
  const [projects, setProjects] = React.useState<ProjectSummary[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [project, setProject] = React.useState<Project | null>(null);
  const [activeTab, setActiveTab] = React.useState<TabKey>("manuscript");
  const [wizardOpen, setWizardOpen] = React.useState(false);
  const [wizardStep, setWizardStep] = React.useState(0);
  const [busy, setBusy] = React.useState<string | null>("加载项目");
  const [toast, setToast] = React.useState<Toast | null>(null);
  const [opsResult, setOpsResult] = React.useState<unknown>(null);
  const [jobs, setJobs] = React.useState<WritingJob[]>([]);
  const [llmConfig, setLlmConfig] = React.useState<LlmConfig | null>(null);
  const [streamingJobId, setStreamingJobId] = React.useState<string | null>(null);
  const [streamEvents, setStreamEvents] = React.useState<JobEvent[]>([]);
  const [streamText, setStreamText] = React.useState<string>("");
  const eventSourceRef = React.useRef<EventSource | null>(null);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [appSettings, setAppSettings] = React.useState<AppSettings | null>(null);
  const [form, setForm] = React.useState({
    title: "镜中之罪",
    theme: "mystery",
    scale: "",
    target_words: 120000,
    language_style: "通俗流畅",
    core_idea: "一个密室案件中，关键线索隐藏在证词的时间差里。",
    special_requirements: "每章必须更新追踪表并保留可审计证据。"
  });

  const latestReport = project?.audit_reports[project.audit_reports.length - 1];
  const hasProject = Boolean(project);

  React.useEffect(() => {
    void refreshProjects();
    void loadLlmConfig();
    void loadSettings();
  }, []);

  const notify = (next: Toast) => {
    setToast(next);
    window.setTimeout(() => setToast(null), 3200);
  };

  const withBusy = async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    try {
      await action();
    } catch (error) {
      notify({ tone: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  };

  async function refreshProjects() {
    await withBusy("刷新项目", async () => {
      const data = await api<{ projects: ProjectSummary[] }>("/api/projects");
      setProjects(data.projects);
      if (!selectedId && data.projects.length) {
        await loadProject(data.projects[0].id);
      }
    });
  }

  async function loadProject(id: string) {
    const data = await api<{ project: Project }>(`/api/projects/${id}`);
    setSelectedId(id);
    setProject(data.project);
  }

  async function loadLlmConfig() {
    try {
      const data = await api<{ config: LlmConfig }>("/api/llm/config");
      setLlmConfig(data.config);
    } catch {
      setLlmConfig(null);
    }
  }

  async function loadSettings() {
    try {
      const data = await api<{ settings: AppSettings }>("/api/settings");
      setAppSettings(data.settings);
    } catch {
      setAppSettings(null);
    }
  }

  const saveSettings = async (payload: Partial<AppSettings>) => {
    await withBusy("保存配置", async () => {
      const data = await api<{ settings: AppSettings }>("/api/settings", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setAppSettings(data.settings);
      await loadLlmConfig();
      notify({ tone: "success", text: "配置已保存并生效" });
    });
  };

  const createProject = async () => {
    await withBusy("创建项目", async () => {
      const payload = {
        ...form,
        target_words: Number(form.target_words || 0)
      };
      const data = await api<{ project: Project }>("/api/projects", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setProject(data.project);
      setSelectedId(data.project.id);
      setWizardOpen(false);
      setWizardStep(0);
      setActiveTab("manuscript");
      notify({ tone: "success", text: "项目已创建" });
      await refreshProjectListOnly(data.project.id);
    });
  };

  const refreshProjectListOnly = async (currentId = selectedId) => {
    const data = await api<{ projects: ProjectSummary[] }>("/api/projects");
    setProjects(data.projects);
    if (currentId) setSelectedId(currentId);
  };

  const runProjectAction = async (label: string, path: string, success: string, body?: unknown) => {
    if (!selectedId) return;
    await withBusy(label, async () => {
      const data = await api<{ project: Project }>(path, {
        method: "POST",
        body: body === undefined ? undefined : JSON.stringify(body)
      });
      setProject(data.project);
      notify({ tone: "success", text: success });
      await refreshProjectListOnly(selectedId);
    });
  };

  const closeEventSource = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  const generateChapter = async () => {
    if (!selectedId) return;
    try {
      setBusy("启动生成任务...");
      const data = await api<{ job_id: string; job: WritingJob }>(
        `/api/projects/${selectedId}/chapters/generate`, { method: "POST" }
      );
      setBusy(null);
      const jobId = data.job_id;
      closeEventSource();
      setStreamingJobId(jobId);
      setStreamEvents([]);
      setStreamText("");
      const successMsg = project?.chapters.length ? "新章节已生成" : "第一章已生成";
      const source = new EventSource(`/api/jobs/${jobId}/stream`);
      eventSourceRef.current = source;
      source.onmessage = (e) => {
        const evt: JobEvent = JSON.parse(e.data as string);
        setStreamEvents((prev) => [...prev, evt]);
        if (evt.event_type === "token" && evt.detail) {
          setStreamText((prev) => prev + evt.detail);
        }
        if (evt.event_type === "completed") {
          closeEventSource();
          setStreamingJobId(null);
          void loadProject(selectedId!);
          void refreshProjectListOnly(selectedId!);
          notify({ tone: "success", text: successMsg });
        } else if (evt.event_type === "failed") {
          closeEventSource();
          setStreamingJobId(null);
          notify({ tone: "danger", text: evt.detail || "生成失败" });
        }
      };
      source.onerror = () => {
        closeEventSource();
        setStreamingJobId(null);
        void loadProject(selectedId!);
        notify({ tone: "warning", text: "进度连接中断，请刷新查看结果" });
      };
    } catch (err) {
      setBusy(null);
      notify({ tone: "danger", text: err instanceof Error ? err.message : String(err) });
    }
  };

  const generateDemo = async () => {
    if (!selectedId) return;
    await withBusy("生成示例章节（三章）...", async () => {
      await api(`/api/projects/${selectedId}/chapters/demo?count=3`, { method: "POST" });
      await loadProject(selectedId!);
      await refreshProjectListOnly(selectedId!);
      notify({ tone: "success", text: "三章示例已生成" });
    });
  };

  const deleteProject = async (id: string, title: string) => {
    if (streamingJobId !== null && selectedId === id) {
      notify({ tone: "warning", text: "章节正在生成中，请等待完成后再删除" });
      return;
    }
    if (!window.confirm(`确定要删除项目「${title}」吗？此操作不可撤销，所有快照和数据将被永久删除。`)) return;
    await withBusy("删除项目", async () => {
      await api(`/api/projects/${id}`, { method: "DELETE" });
      if (selectedId === id) {
        setSelectedId(null);
        setProject(null);
      }
      await refreshProjectListOnly();
      notify({ tone: "warning", text: `项目「${title}」已删除` });
    });
  };

  const suggestParams = async () => {
    await withBusy("生成建议", async () => {
      const data = await api<{ suggestions: unknown }>("/api/params/suggest", {
        method: "POST",
        body: JSON.stringify({ theme: form.theme, core_idea: form.core_idea })
      });
      setOpsResult(data.suggestions);
      notify({ tone: "success", text: "建议已生成，可在右侧查看" });
    });
  };

  const refineIdea = async () => {
    await withBusy("优化创意", async () => {
      const data = await api<{ result: { refined: string } }>("/api/params/refine", {
        method: "POST",
        body: JSON.stringify({ text: form.core_idea })
      });
      setForm((prev) => ({ ...prev, core_idea: data.result.refined }));
      notify({ tone: "success", text: "核心创意已优化" });
    });
  };

  const checkpoint = async (type: "manual" | "arc" | "volume" | "emergency") => {
    if (!selectedId) return;
    if (type === "emergency" && !window.confirm("应急快照会永久保留当前状态，确定创建吗？")) return;
    await withBusy("创建快照", async () => {
      const data = await api<{ checkpoint: Checkpoint }>(`/api/projects/${selectedId}/${type}_checkpoint`, {
        method: "POST"
      });
      setOpsResult(data.checkpoint);
      notify({ tone: "success", text: "快照已创建" });
      await loadProject(selectedId);
      await refreshProjectListOnly(selectedId);
    });
  };

  const showRestoreDiff = async (id: string) => {
    if (!selectedId) return;
    await withBusy("读取恢复差异", async () => {
      const data = await api<{ diff: unknown }>(`/api/projects/${selectedId}/restore_diff/${id}`);
      setOpsResult(data.diff);
      setActiveTab("advanced");
    });
  };

  const restoreCheckpoint = async (id: string) => {
    if (!selectedId) return;
    if (!window.confirm("恢复快照会回滚章节和追踪表状态，确定继续吗？")) return;
    await withBusy("恢复快照", async () => {
      const data = await api<{ project: Project }>(`/api/projects/${selectedId}/restore/${id}`, { method: "POST" });
      setProject(data.project);
      notify({ tone: "warning", text: "项目已恢复到所选快照" });
      await refreshProjectListOnly(selectedId);
    });
  };

  const renderJobs = async () => {
    await withBusy("读取任务状态", async () => {
      const data = await api<{ jobs: WritingJob[] }>("/api/jobs");
      setJobs(data.jobs);
      setActiveTab("advanced");
    });
  };

  const jobAction = async (jobId: string, action: string) => {
    if (["cancel"].includes(action) && !window.confirm("确定取消这个任务吗？")) return;
    await withBusy("更新任务", async () => {
      await api(`/api/jobs/${jobId}/${action}`, { method: "POST" });
      await renderJobs();
    });
  };

  const scan = async () => {
    if (!selectedId) return;
    await withBusy("全局扫描", async () => {
      const data = await api<{ findings: unknown }>(`/api/projects/${selectedId}/scan`);
      setOpsResult(data.findings);
      setActiveTab("advanced");
    });
  };

  const volumeBridge = async (confirm = false) => {
    if (!selectedId) return;
    await withBusy(confirm ? "确认桥接" : "生成桥接", async () => {
      const path = confirm
        ? `/api/projects/${selectedId}/confirm_volume_bridge`
        : `/api/projects/${selectedId}/volume_bridge`;
      const data = await api<{ bridge: unknown }>(path, { method: "POST" });
      setOpsResult(data.bridge);
      notify({ tone: "success", text: confirm ? "VolumeBridge 已确认" : "VolumeBridge 已生成" });
      await loadProject(selectedId);
    });
  };

  const downloadExport = async (type: string) => {
    if (!selectedId) return;
    await withBusy("准备导出", async () => {
      const data = await api<{ export: { filename: string; content_type: string; content: string } }>(
        `/api/projects/${selectedId}/export/${type}`
      );
      const exported = data.export;
      let content: BlobPart = exported.content;
      if (["docx", "pdf"].includes(type)) {
        const binary = atob(exported.content);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
        content = bytes;
      }
      const blob = new Blob([content], { type: exported.content_type });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = exported.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      notify({ tone: "success", text: "导出已开始" });
    });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Bot size={22} /></div>
          <div>
            <h1>Book Agent</h1>
            <p>小说生成与审计工作台</p>
          </div>
        </div>
        <button className="primary wide" onClick={() => setWizardOpen(true)}>
          <Sparkles size={18} /> 创建新项目
        </button>
        <div className="sidebar-heading">
          <span>项目</span>
          <button className="icon-button" onClick={() => void refreshProjects()} title="刷新项目">
            <RefreshCw size={16} />
          </button>
        </div>
        <div className="project-list">
          {projects.length === 0 ? (
            <div className="empty-mini">暂无项目，点击上方「创建新项目」开始。</div>
          ) : (
            projects.map((item) => (
              <div
                className={`project-card ${item.id === selectedId ? "active" : ""}`}
                key={item.id}
                onClick={() => void withBusy("载入项目", () => loadProject(item.id))}
              >
                <div className="project-card-main">
                  <strong>{item.title}</strong>
                  <span>{themeLabels[item.theme] || item.theme} · {item.chapter_count} 章</span>
                  {item.latest_status && <StatusBadge status={item.latest_status} />}
                </div>
                <button
                  className="icon-button danger-text project-delete-btn"
                  title={`删除「${item.title}」`}
                  onClick={(e) => { e.stopPropagation(); void deleteProject(item.id, item.title); }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h2>{project?.meta.title || "选择或创建项目"}</h2>
            <p>
              {project
                ? `${themeLabels[project.meta.theme] || project.meta.theme} · ${scaleLabels[project.meta.scale] || project.meta.scale} · ${String(project.creation_params.core_idea || "")}`
                : "主流程会引导你完成创建、生成、审计和导出。"}
            </p>
          </div>
          <div className="topbar-actions">
            {llmConfig && (
              <span className="llm-pill" title="当前大模型配置">
                <Gauge size={15} /> {llmConfig.provider} · {llmConfig.model}{llmConfig.provider !== "mock" ? " · 流式" : ""}
              </span>
            )}
            <button className="icon-button" title="配置" onClick={() => { void loadSettings(); setSettingsOpen(true); }}>
              <Settings size={18} />
            </button>
            {hasProject && (
              <>
                <button className="secondary" onClick={() => void loadProject(selectedId || "")}>
                  <RefreshCw size={16} /> 重新载入
                </button>
                <button
                  className="primary"
                  onClick={() => void generateChapter()}
                  disabled={streamingJobId !== null}
                >
                  {streamingJobId ? <Loader2 size={17} className="spin" /> : <Wand2 size={17} />}
                  {streamingJobId ? "生成中..." : project?.chapters.length ? "继续生成" : "生成第一章"}
                </button>
              </>
            )}
          </div>
        </header>

        {project ? (
          <>
            <section className="summary-grid">
              <Metric icon={BookOpen} label="章节" value={`${project.chapters.length}`} />
              <Metric icon={ClipboardCheck} label="最新审计" value={latestReport?.overall_status || "未审计"} status={latestReport?.overall_status} />
              <Metric icon={Database} label="追踪表" value={`${Object.keys(project.theme_tracking_tables).length}`} />
              <Metric icon={Save} label="快照" value={`${project.checkpoints.length}`} />
            </section>

            <section className="next-step">
              <div>
                <strong>{nextStepTitle(project, latestReport)}</strong>
                <p>{nextStepHint(project, latestReport)}</p>
              </div>
              <div className="next-actions">
                {latestReport?.overall_status === "warning" && (
                  <>
                    <button className="secondary" onClick={() => void runProjectAction("修订章节", `/api/projects/${selectedId}/revise`, "修订稿已生成")}>
                      <RotateCcw size={16} /> 修订
                    </button>
                    <button className="secondary" onClick={() => void runProjectAction("接受警告", `/api/projects/${selectedId}/accept_warnings`, "已接受警告")}>
                      <Check size={16} /> 接受警告
                    </button>
                  </>
                )}
                {latestReport?.overall_status === "fail" && (
                  <button className="secondary danger-text" onClick={() => void runProjectAction("标记人工审核", `/api/projects/${selectedId}/manual_review`, "已进入人工审核")}>
                    <ShieldAlert size={16} /> 人工审核
                  </button>
                )}
                <button className="secondary" onClick={() => void generateDemo()} disabled={streamingJobId !== null}>
                  <Sparkles size={16} /> 生成示例章节
                </button>
              </div>
            </section>

            {streamingJobId && (
              <StreamProgressPanel jobId={streamingJobId} events={streamEvents} streamText={streamText} />
            )}

            <nav className="tabs">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button key={tab.key} className={activeTab === tab.key ? "active" : ""} onClick={() => setActiveTab(tab.key)}>
                    <Icon size={17} /> {tab.label}
                  </button>
                );
              })}
            </nav>

            <section className="content-panel">
              {activeTab === "manuscript" && <ManuscriptPanel chapters={project.chapters} onGenerate={() => void generateChapter()} generating={streamingJobId !== null} />}
              {activeTab === "audit" && <AuditPanel report={latestReport} />}
              {activeTab === "tracking" && <TrackingPanel tables={project.theme_tracking_tables} />}
              {activeTab === "snapshots" && (
                <SnapshotPanel checkpoints={project.checkpoints} onDiff={showRestoreDiff} onRestore={restoreCheckpoint} />
              )}
              {activeTab === "export" && <ExportPanel onExport={downloadExport} />}
              {activeTab === "advanced" && (
                <AdvancedPanel
                  jobs={jobs}
                  opsResult={opsResult}
                  onRefreshJobs={renderJobs}
                  onJobAction={jobAction}
                  onScan={scan}
                  onCheckpoint={checkpoint}
                  onVolumeBridge={volumeBridge}
                  llmConfig={llmConfig}
                  reloadLlm={() => void withBusy("重载 LLM 配置", async () => {
                    await api("/api/llm/reload", { method: "POST" });
                    await loadLlmConfig();
                    notify({ tone: "success", text: "LLM 配置已重新加载" });
                  })}
                />
              )}
            </section>
          </>
        ) : (
          <section className="welcome">
            <Sparkles size={38} />
            <h2>从一本新书开始</h2>
            <p>用三步创建项目，然后让系统生成章节、审计一致性、维护追踪表和快照。</p>
            <button className="primary" onClick={() => setWizardOpen(true)}>
              创建新项目 <ChevronRight size={17} />
            </button>
          </section>
        )}
      </main>

      {wizardOpen && (
        <ProjectWizard
          form={form}
          step={wizardStep}
          setStep={setWizardStep}
          setForm={setForm}
          onClose={() => setWizardOpen(false)}
          onCreate={createProject}
          onSuggest={suggestParams}
          onRefine={refineIdea}
        />
      )}

      {settingsOpen && appSettings && (
        <SettingsModal
          settings={appSettings}
          onClose={() => setSettingsOpen(false)}
          onSave={saveSettings}
        />
      )}

      {busy && <BusyOverlay label={busy} />}
      {toast && <div className={`toast ${toast.tone}`}>{toast.text}</div>}
    </div>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const label = status === "pass" ? "通过" : status === "warning" ? "警告" : status === "fail" ? "未通过" : status;
  const icon = status === "pass" ? <Check size={14} /> : status === "warning" ? <AlertTriangle size={14} /> : <XCircle size={14} />;
  return <span className={`status-badge ${status}`}>{icon}{label}</span>;
}

function Metric({
  icon: Icon,
  label,
  value,
  status
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  status?: Status;
}) {
  return (
    <div className="metric">
      <Icon size={20} />
      <span>{label}</span>
      <strong className={status ? `status-text ${status}` : ""}>{value}</strong>
    </div>
  );
}

function nextStepTitle(project: Project, report?: AuditReport) {
  if (!project.chapters.length) return "下一步：生成第一章";
  if (report?.overall_status === "fail") return "存在需要处理的阻塞问题";
  if (report?.overall_status === "warning") return "审计发现潜在问题，可修订后继续或接受并跳过";
  return "状态良好，可以继续写下一章";
}

function nextStepHint(project: Project, report?: AuditReport) {
  if (!project.chapters.length) return "生成后会自动执行审计、更新追踪表并保存快照。";
  if (report?.overall_status === "fail") return "建议先修订或标记人工审核，再继续生成。";
  if (report?.overall_status === "warning") return `发现 ${report.warning_count} 条警告，处理后再继续会更稳。`;
  return "当前章节已通过审计，系统已保存可恢复快照。";
}

function jobStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    paused: "已暂停",
    cancelled: "已取消",
    failed: "失败",
    completed: "已完成",
  };
  return labels[status] || status;
}

function ManuscriptPanel({ chapters, onGenerate, generating }: { chapters: Chapter[]; onGenerate: () => void; generating?: boolean }) {
  if (!chapters.length) {
    return (
      <div className="empty-state">
        <FileText size={34} />
        <h3>尚无章节内容</h3>
        <p>点击"生成第一章"后，这里会显示正文、章节编号和创建时间。</p>
        <button className="primary" onClick={onGenerate} disabled={generating}>
          {generating ? <Loader2 size={17} className="spin" /> : <Wand2 size={17} />} 生成第一章
        </button>
      </div>
    );
  }
  return (
    <div className="chapter-list">
      {chapters.map((chapter) => (
        <article className="chapter-card" key={chapter.id}>
          <div className="chapter-head">
            <span>第 {chapter.chapter_no} 章</span>
            <time>{new Date(chapter.created_at).toLocaleString()}</time>
          </div>
          <h3>{chapter.title}</h3>
          <p>{chapter.text}</p>
        </article>
      ))}
    </div>
  );
}

function AuditPanel({ report }: { report?: AuditReport }) {
  if (!report) return <Empty icon={ClipboardCheck} title="尚未生成审计报告" text="生成章节后会自动执行通用审计和题材审计。" />;
  return (
    <div className="audit-panel">
      <div className="audit-summary">
        <StatusBadge status={report.overall_status} />
        <strong>评分 {(report.score * 100).toFixed(0)}</strong>
        <span>{report.decision}</span>
      </div>
      <div className="finding-list">
        {report.findings.map((finding) => (
          <div className="finding" key={finding.id}>
            <StatusBadge status={finding.status} />
            <div>
              <strong>{finding.rule}</strong>
              <p>{finding.detail}</p>
              {finding.suggested_fix && <small>{finding.suggested_fix}</small>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrackingPanel({ tables }: { tables: Record<string, Array<Record<string, unknown>>> }) {
  const entries = Object.entries(tables);
  if (!entries.length) return <Empty icon={Table2} title="暂无追踪表" text="项目创建后会自动生成题材专属追踪表。" />;
  return (
    <div className="table-list">
      {entries.map(([tableId, rows]) => (
        <details key={tableId} open={rows.length > 0}>
          <summary>{tableId}<span>{rows.length} 行</span></summary>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {Object.keys(rows[0] || { status: "" }).slice(0, 6).map((key) => <th key={key}>{key}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.length ? rows.map((row, index) => (
                  <tr key={index}>
                    {Object.keys(rows[0]).slice(0, 6).map((key) => <td key={key}>{String(row[key] ?? "")}</td>)}
                  </tr>
                )) : (
                  <tr><td>暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </details>
      ))}
    </div>
  );
}

function SnapshotPanel({
  checkpoints,
  onDiff,
  onRestore
}: {
  checkpoints: Checkpoint[];
  onDiff: (id: string) => Promise<void>;
  onRestore: (id: string) => Promise<void>;
}) {
  if (!checkpoints.length) return <Empty icon={History} title="尚未保存快照" text="生成章节后会自动保存断点快照。" />;
  return (
    <div className="snapshot-list">
      {checkpoints.map((checkpoint) => (
        <div className="snapshot-row" key={checkpoint.id}>
          <div>
            <strong>{checkpoint.type}</strong>
            <span>第 {checkpoint.chapter_no || "-"} 章 · {checkpoint.retention_policy} · {new Date(checkpoint.created_at).toLocaleString()}</span>
          </div>
          <div>
            <button className="secondary" onClick={() => void onDiff(checkpoint.id)}><Search size={15} /> 差异</button>
            <button className="secondary danger-text" onClick={() => void onRestore(checkpoint.id)}><RotateCcw size={15} /> 恢复</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function ExportPanel({ onExport }: { onExport: (type: string) => Promise<void> }) {
  const exports = [
    ["manuscript_md", "Markdown 草稿", FileText],
    ["audit_json", "审计 JSON", ClipboardCheck],
    ["tracking_json", "追踪表 JSON", Table2],
    ["snapshot_json", "项目快照 JSON", Save],
    ["volume_bridge_json", "VolumeBridge JSON", Archive],
    ["docx", "DOCX 文档", FileText],
    ["pdf", "PDF 文件", FileText]
  ] as const;
  return (
    <div className="export-grid">
      {exports.map(([type, label, Icon]) => (
        <button className="export-card" key={type} onClick={() => void onExport(type)}>
          <Icon size={22} />
          <strong>{label}</strong>
          <span>下载</span>
        </button>
      ))}
    </div>
  );
}

function AdvancedPanel({
  jobs,
  opsResult,
  onRefreshJobs,
  onJobAction,
  onScan,
  onCheckpoint,
  onVolumeBridge,
  llmConfig,
  reloadLlm
}: {
  jobs: WritingJob[];
  opsResult: unknown;
  onRefreshJobs: () => Promise<void>;
  onJobAction: (jobId: string, action: string) => Promise<void>;
  onScan: () => Promise<void>;
  onCheckpoint: (type: "manual" | "arc" | "volume" | "emergency") => Promise<void>;
  onVolumeBridge: (confirm?: boolean) => Promise<void>;
  llmConfig: LlmConfig | null;
  reloadLlm: () => void;
}) {
  return (
    <div className="advanced-grid">
      <section>
        <h3>任务</h3>
        <div className="button-row">
          <button className="secondary" onClick={() => void onRefreshJobs()}><RefreshCw size={16} /> 刷新任务</button>
          <button className="secondary" onClick={() => void onScan()}><Search size={16} /> 全局扫描</button>
        </div>
        {jobs.length ? jobs.map((job) => (
          <div className="job-row" key={job.id}>
            <div>
              <strong>{job.type}</strong>
              <span>{jobStatusLabel(job.status)} · {job.current_step}</span>
              {job.last_llm_record && (
                <span className="llm-stats">
                  输入 {job.last_llm_record.prompt_tokens_estimate} / 输出 {job.last_llm_record.output_tokens_estimate} token · 耗时 {job.last_llm_record.latency_ms}ms{job.last_llm_record.cost_estimate > 0 ? ` · ¥${job.last_llm_record.cost_estimate.toFixed(4)}` : ""}
                </span>
              )}
            </div>
            <div>
              <button className="icon-button" title="暂停" onClick={() => void onJobAction(job.id, "pause")}><Pause size={15} /></button>
              <button className="icon-button" title="继续" onClick={() => void onJobAction(job.id, "resume")}><Play size={15} /></button>
              <button className="icon-button" title="重试" onClick={() => void onJobAction(job.id, "retry")}><RotateCcw size={15} /></button>
            </div>
          </div>
        )) : <p className="muted">暂无任务记录。</p>}
      </section>
      <section>
        <h3>快照与桥接</h3>
        <div className="button-grid">
          <button className="secondary" onClick={() => void onCheckpoint("manual")}><Save size={16} /> 手动快照</button>
          <button className="secondary" onClick={() => void onCheckpoint("arc")}><Save size={16} /> 情节弧快照</button>
          <button className="secondary" onClick={() => void onCheckpoint("volume")}><Archive size={16} /> 分卷快照</button>
          <button className="secondary danger-text" onClick={() => void onCheckpoint("emergency")}><ShieldAlert size={16} /> 紧急快照</button>
          <button className="secondary" onClick={() => void onVolumeBridge(false)}><Archive size={16} /> 生成桥接</button>
          <button className="secondary" onClick={() => void onVolumeBridge(true)}><Check size={16} /> 确认桥接</button>
        </div>
      </section>
      <section>
        <h3>大模型</h3>
        {llmConfig ? (
          <div className="llm-config">
            <span>Provider：{llmConfig.provider}</span>
            <span>Model：{llmConfig.model}</span>
            <span>Key：{llmConfig.api_key_configured ? "已配置" : "未配置"}</span>
            <span>Temperature：{llmConfig.temperature}</span>
            <button className="secondary" onClick={reloadLlm}><RefreshCw size={16} /> 重新加载</button>
          </div>
        ) : <p className="muted">无法读取 LLM 配置。</p>}
      </section>
      <section>
        <h3>操作结果</h3>
        <pre>{opsResult ? JSON.stringify(opsResult, null, 2) : "暂无操作结果"}</pre>
      </section>
    </div>
  );
}

function ProjectWizard({
  form,
  step,
  setStep,
  setForm,
  onClose,
  onCreate,
  onSuggest,
  onRefine
}: {
  form: {
    title: string;
    theme: string;
    scale: string;
    target_words: number;
    language_style: string;
    core_idea: string;
    special_requirements: string;
  };
  step: number;
  setStep: (step: number) => void;
  setForm: React.Dispatch<React.SetStateAction<typeof form>>;
  onClose: () => void;
  onCreate: () => Promise<void>;
  onSuggest: () => Promise<void>;
  onRefine: () => Promise<void>;
}) {
  const update = (key: keyof typeof form, value: string | number) => setForm((prev) => ({ ...prev, [key]: value }));
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-head">
          <div>
            <h2>创建新项目</h2>
            <p>第 {step + 1} 步，共 3 步</p>
          </div>
          <button className="icon-button" onClick={onClose}><XCircle size={18} /></button>
        </div>
        <div className="stepper">
          {["基础信息", "写作目标", "确认"].map((label, index) => <span className={index <= step ? "active" : ""} key={label}>{label}</span>)}
        </div>
        {step === 0 && (
          <div className="form-grid">
            <label>书名<input value={form.title} onChange={(event) => update("title", event.target.value)} /></label>
            <label>题材<select value={form.theme} onChange={(event) => update("theme", event.target.value)}>
              <option value="mystery">推理</option>
              <option value="sci_fi">科幻</option>
              <option value="xuanhuan">玄幻</option>
            </select></label>
            <label>核心创意<textarea value={form.core_idea} onChange={(event) => update("core_idea", event.target.value)} /></label>
          </div>
        )}
        {step === 1 && (
          <div className="form-grid">
            <label>篇幅<select value={form.scale} onChange={(event) => update("scale", event.target.value)}>
              <option value="">按目标字数自动</option>
              <option value="micro">微型</option>
              <option value="short">短篇</option>
              <option value="medium">中篇</option>
              <option value="long">长篇</option>
              <option value="epic">超长篇</option>
            </select></label>
            <label>目标字数<input type="number" value={form.target_words} onChange={(event) => update("target_words", Number(event.target.value))} /></label>
            <label>语言风格<input value={form.language_style} onChange={(event) => update("language_style", event.target.value)} /></label>
            <label>特殊要求<textarea value={form.special_requirements} onChange={(event) => update("special_requirements", event.target.value)} /></label>
          </div>
        )}
        {step === 2 && (
          <div className="confirm-box">
            <h3>{form.title}</h3>
            <p>{themeLabels[form.theme]} · {form.scale ? scaleLabels[form.scale] : "按目标字数自动"} · {form.target_words.toLocaleString()} 字</p>
            <p>{form.core_idea}</p>
          </div>
        )}
        <div className="modal-actions">
          <button className="secondary" onClick={() => void onSuggest()}><Sparkles size={16} /> 建议</button>
          <button className="secondary" onClick={() => void onRefine()}><Wand2 size={16} /> 优化创意</button>
          <div className="spacer" />
          {step > 0 && <button className="secondary" onClick={() => setStep(step - 1)}>上一步</button>}
          {step < 2 ? (
            <button className="primary" onClick={() => setStep(step + 1)}>下一步 <ChevronRight size={16} /></button>
          ) : (
            <button className="primary" onClick={() => void onCreate()}><Check size={16} /> 创建</button>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsModal({
  settings,
  onClose,
  onSave
}: {
  settings: AppSettings;
  onClose: () => void;
  onSave: (payload: Partial<AppSettings>) => Promise<void>;
}) {
  const [form, setForm] = React.useState({
    llm_provider: settings.llm_provider,
    openai_api_key: "",
    openai_base_url: settings.openai_base_url,
    openai_model: settings.openai_model,
    llm_system_prompt: settings.llm_system_prompt,
    llm_temperature: String(settings.llm_temperature),
    llm_max_tokens: settings.llm_max_tokens != null ? String(settings.llm_max_tokens) : "",
    llm_max_retries: String(settings.llm_max_retries),
    llm_prompt_token_cost: String(settings.llm_prompt_token_cost),
    llm_completion_token_cost: String(settings.llm_completion_token_cost),
    llm_no_proxy: settings.llm_no_proxy,
  });
  const [showKey, setShowKey] = React.useState(false);

  const upd = (key: keyof typeof form, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSave = async () => {
    const payload: Record<string, unknown> = {
      llm_provider: form.llm_provider,
      openai_base_url: form.openai_base_url,
      openai_model: form.openai_model,
      llm_system_prompt: form.llm_system_prompt,
      llm_temperature: parseFloat(form.llm_temperature) || 0.4,
      llm_max_tokens: form.llm_max_tokens ? parseInt(form.llm_max_tokens, 10) : null,
      llm_max_retries: parseInt(form.llm_max_retries, 10) || 2,
      llm_prompt_token_cost: parseFloat(form.llm_prompt_token_cost) || 0,
      llm_completion_token_cost: parseFloat(form.llm_completion_token_cost) || 0,
      llm_no_proxy: form.llm_no_proxy,
    };
    if (form.openai_api_key.trim()) {
      payload.openai_api_key = form.openai_api_key.trim();
    }
    await onSave(payload as Partial<AppSettings>);
    onClose();
  };

  return (
    <div className="modal-backdrop">
      <div className="modal modal-wide">
        <div className="modal-head">
          <div>
            <h2>配置</h2>
            <p>设置保存到本地文件，优先级高于环境变量</p>
          </div>
          <button className="icon-button" onClick={onClose}><XCircle size={18} /></button>
        </div>

        <div className="settings-grid">
          <div className="settings-section">
            <h3>LLM Provider</h3>
            <label>Provider
              <select value={form.llm_provider} onChange={(e) => upd("llm_provider", e.target.value)}>
                <option value="openai_compatible">OpenAI Compatible</option>
                <option value="mock">Mock（仅测试）</option>
              </select>
            </label>
            <label>API Base URL
              <input
                value={form.openai_base_url}
                onChange={(e) => upd("openai_base_url", e.target.value)}
                placeholder="https://api.openai.com/v1/chat/completions"
              />
            </label>
            <label>
              API Key
              {settings.openai_api_key_set && (
                <span className="settings-hint">（当前已配置，留空保持不变，输入新值覆盖）</span>
              )}
              <div className="input-with-icon">
                <input
                  type={showKey ? "text" : "password"}
                  value={form.openai_api_key}
                  onChange={(e) => upd("openai_api_key", e.target.value)}
                  placeholder={settings.openai_api_key_set ? "留空保持当前值" : "输入 API Key"}
                  autoComplete="off"
                />
                <button className="icon-button input-eye" onClick={() => setShowKey((v) => !v)} type="button">
                  {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </label>
            <label>模型名称
              <input
                value={form.openai_model}
                onChange={(e) => upd("openai_model", e.target.value)}
                placeholder="gpt-4o-mini"
              />
            </label>
          </div>

          <div className="settings-section">
            <h3>生成参数</h3>
            <label>Temperature（0.0 – 1.0）
              <input
                type="number" min="0" max="1" step="0.05"
                value={form.llm_temperature}
                onChange={(e) => upd("llm_temperature", e.target.value)}
              />
            </label>
            <label>最大输出 Token（留空不限制）
              <input
                type="number" min="1"
                value={form.llm_max_tokens}
                onChange={(e) => upd("llm_max_tokens", e.target.value)}
                placeholder="留空不限制"
              />
            </label>
            <label>失败重试次数
              <input
                type="number" min="0" max="10"
                value={form.llm_max_retries}
                onChange={(e) => upd("llm_max_retries", e.target.value)}
              />
            </label>
            <label>输入 Token 费用（每 1K）
              <input
                type="number" min="0" step="0.0001"
                value={form.llm_prompt_token_cost}
                onChange={(e) => upd("llm_prompt_token_cost", e.target.value)}
              />
            </label>
            <label>输出 Token 费用（每 1K）
              <input
                type="number" min="0" step="0.0001"
                value={form.llm_completion_token_cost}
                onChange={(e) => upd("llm_completion_token_cost", e.target.value)}
              />
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={form.llm_no_proxy}
                onChange={(e) => upd("llm_no_proxy", e.target.checked)}
              />
              禁用系统代理（no_proxy）
            </label>
          </div>

          <div className="settings-section settings-section-wide">
            <h3>System Prompt</h3>
            <label>
              <textarea
                rows={5}
                value={form.llm_system_prompt}
                onChange={(e) => upd("llm_system_prompt", e.target.value)}
                placeholder="你是一个严谨的长篇小说写作助手..."
              />
            </label>
          </div>
        </div>

        <div className="modal-actions">
          <div className="spacer" />
          <button className="secondary" onClick={onClose}>取消</button>
          <button className="primary" onClick={() => void handleSave()}><Check size={16} /> 保存</button>
        </div>
      </div>
    </div>
  );
}

function StreamProgressPanel({ jobId, events, streamText }: { jobId: string; events: JobEvent[]; streamText: string }) {
  const latest = events[events.length - 1];
  const progress = latest?.progress ?? 0;
  const stepLabel = latest?.step || "排队中";
  const llmRec = latest?.llm_record;
  const streamTokens = latest?.stream_tokens_out ?? 0;
  const previewRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (previewRef.current) {
      previewRef.current.scrollTop = previewRef.current.scrollHeight;
    }
  }, [streamText]);

  return (
    <div className="stream-panel">
      <div className="stream-header">
        <Loader2 size={16} className="spin" />
        <strong>生成中</strong>
        <span className="muted">{jobId.slice(0, 12)}…</span>
      </div>
      <div className="stream-bar-wrap">
        <div className="stream-bar" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <div className="stream-step">{stepLabel} · {Math.round(progress * 100)}%</div>
      {llmRec ? (
        <div className="stream-stats">
          输入 {llmRec.prompt_tokens_estimate} / 输出 {llmRec.output_tokens_estimate} token · 耗时 {llmRec.latency_ms}ms{llmRec.cost_estimate > 0 ? ` · ¥${llmRec.cost_estimate.toFixed(4)}` : ""}
        </div>
      ) : streamTokens > 0 ? (
        <div className="stream-stats">
          已输出 {streamTokens} token…
        </div>
      ) : null}
      {streamText && (
        <div className="stream-text-preview" ref={previewRef}>{streamText}</div>
      )}
    </div>
  );
}

function Empty({ icon: Icon, title, text }: { icon: LucideIcon; title: string; text: string }) {
  return (
    <div className="empty-state">
      <Icon size={34} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

function BusyOverlay({ label }: { label: string }) {
  return (
    <div className="busy-overlay">
      <div><Loader2 size={18} className="spin" /> {label}</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
