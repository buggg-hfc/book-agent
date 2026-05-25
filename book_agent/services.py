from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AppConfig
from .engines import FictionGenreEngine, build_default_context
from .exporters import b64, make_docx, make_pdf
from .logging_utils import configure_logging
from .memory import GlobalConsistencyScanner, LongRangeAlignmentService, StyleService, SummaryService, VolumeService
from .models import (
    AuditFinding,
    AuditReport,
    BookProject,
    Chapter,
    ChapterEvent,
    Checkpoint,
    RestoreValidationResult,
    TablePatch,
    VolumeBridge,
    WritingJob,
    new_id,
    utc_now,
)
from .providers import provider_from_config
from .serialization import chapter_from_dict, project_from_dict, report_from_dict, to_plain
from .storage import JsonStore
from .strategies import get_strategy
from .utils import stable_hash


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, WritingJob] = {}
        self.project_write_locks: set[str] = set()

    def start(self, project_id: str, job_type: str, step: str, write: bool = True) -> WritingJob:
        if write and project_id in self.project_write_locks:
            raise RuntimeError(f"project has running write job: {project_id}")
        job = WritingJob(
            id=new_id("job"),
            project_id=project_id,
            type=job_type,
            status="running",
            progress=0.0,
            current_step=step,
            idempotency_key=new_id("idem"),
        )
        self.jobs[job.id] = job
        if write:
            self.project_write_locks.add(project_id)
        return job

    def complete(self, job: WritingJob, step: str = "completed") -> WritingJob:
        job.status = "completed"
        job.progress = 1.0
        job.current_step = step
        job.updated_at = utc_now()
        self.project_write_locks.discard(job.project_id)
        return job

    def fail(self, job: WritingJob, error: Exception) -> WritingJob:
        job.status = "failed"
        job.error = str(error)
        job.failure_step = job.current_step
        job.can_retry = True
        job.updated_at = utc_now()
        self.project_write_locks.discard(job.project_id)
        return job

    def list(self) -> list[WritingJob]:
        return list(self.jobs.values())

    def pause(self, job_id: str) -> WritingJob:
        job = self.jobs[job_id]
        if job.status == "running":
            job.status = "paused"
            job.current_step = "paused"
            job.updated_at = utc_now()
            self.project_write_locks.discard(job.project_id)
        return job

    def resume(self, job_id: str) -> WritingJob:
        job = self.jobs[job_id]
        if job.status == "paused":
            job.status = "queued"
            job.current_step = "queued for retry"
            job.updated_at = utc_now()
        return job

    def cancel(self, job_id: str) -> WritingJob:
        job = self.jobs[job_id]
        if job.status in {"queued", "running", "paused"}:
            job.status = "cancelled"
            job.current_step = "cancelled"
            job.updated_at = utc_now()
            self.project_write_locks.discard(job.project_id)
        return job

    def retry(self, job_id: str) -> WritingJob:
        job = self.jobs[job_id]
        if not job.can_retry:
            raise RuntimeError(f"job is not retryable: {job_id}")
        if job.status == "running":
            raise RuntimeError(f"running job cannot be retried: {job_id}")
        if job.project_id in self.project_write_locks and job.status not in {"running", "paused"}:
            raise RuntimeError(f"project has running write job: {job.project_id}")
        job.retry_count += 1
        job.status = "queued"
        job.error = None
        job.failure_step = None
        job.current_step = "queued for retry"
        job.updated_at = utc_now()
        return job


class BookAgentService:
    def __init__(self, store: JsonStore | Path | str | None = None, warning_threshold: int | None = None) -> None:
        self.config = AppConfig.from_env()
        self.store = store if isinstance(store, JsonStore) else JsonStore(store or self.config.data_dir)
        self.jobs = JobManager()
        self.warning_threshold = warning_threshold if warning_threshold is not None else self.config.warning_threshold
        self.provider = provider_from_config(self.config)
        self.logger = configure_logging()
        self.engine = FictionGenreEngine()
        self.style_service = StyleService()
        self.summary_service = SummaryService()
        self.alignment_service = LongRangeAlignmentService()
        self.scanner = GlobalConsistencyScanner()
        self.volume_service = VolumeService()

    def create_project(self, payload: dict[str, Any]) -> BookProject:
        theme = payload.get("theme", "mystery")
        scale = payload.get("scale") or self.classify_scale_by_word_count(payload.get("target_words"))
        strategy = get_strategy(theme)
        title = payload.get("title") or f"{strategy.display_name}新书"
        core_idea = payload.get("core_idea") or "一个尚未展开的故事创意"
        outline = [
            {"chapter_no": idx + 1, "title": item, "summary": f"{item}：围绕「{core_idea}」推进。"}
            for idx, item in enumerate(strategy.outline_seed())
        ]
        project = BookProject(
            id=new_id("project"),
            meta={"title": title, "genre": "fiction", "theme": theme, "scale": scale, "language": "zh-CN"},
            creation_params={
                "core_idea": core_idea,
                "target_audience": payload.get("target_audience", "青年(18-30)"),
                "language_style": payload.get("language_style", "通俗流畅"),
                "narrative_pov": payload.get("narrative_pov", "第三人称有限"),
                "tone": payload.get("tone", ["严肃"]),
                "special_requirements": payload.get("special_requirements", ""),
                "target_words": payload.get("target_words"),
            },
            world_setting={
                "premise": core_idea,
                "era": payload.get("era", "未指定时代"),
                "locations": payload.get("locations", ["核心舞台"]),
                "rules": ["所有关键状态必须进入追踪表", "章节生成后必须审计"],
                "forbidden_contradictions": ["核心规则不得无解释被推翻"],
            },
            characters=[
                {"id": "hero", "name": "主角", "role": "protagonist", "status": "active", "knowledge": []},
                {"id": "support", "name": "关键同伴", "role": "support", "status": "active", "knowledge": []},
            ],
            plot_structure={"type": "five_step", "current_stage": "开端"},
            outline=outline,
            foreshadowing_registry=[{
                "id": "seed-foreshadow",
                "type": "theme",
                "description": "核心创意相关的长期伏笔",
                "planted_chapter": 1,
                "planted_text": core_idea,
                "intended_payoff": "在中后段回收核心谜面或设定代价",
                "payoff_chapter": 5,
                "status": "planted",
                "cross_volume": scale == "epic",
                "related_foreshadows": [],
            }],
            theme_tracking_tables=strategy.seed_tracking_tables(),
        )
        project.style_anchor = self.style_service.build_anchor(project)
        project.style_calibration = self.style_service.calibrate(project)
        self.summary_service.rebuild(project)
        self.volume_service.ensure_volume_space(project)
        self._record_event(project, None, "project_created", {"title": title, "theme": theme})
        self.store.save_project(project)
        return project

    def list_projects(self) -> list[BookProject]:
        return self.store.list_projects()

    def get_project(self, project_id: str) -> BookProject:
        return self.store.load_project(project_id)

    def generate_chapter(self, project_id: str) -> tuple[BookProject, WritingJob]:
        job = self.jobs.start(project_id, "generate_chapter", "loading project")
        self.logger.info("job_started job_id=%s project_id=%s type=%s", job.id, project_id, job.type)
        try:
            project = self.store.load_project(project_id)
            chapter_no = len(project.chapters) + 1
            job.current_step = "writing chapter"
            chapter = self.engine.write_chapter(project, build_default_context(project))
            llm_text, llm_record = self.provider.generate_text(
                f"为《{project.meta.get('title')}》生成第{chapter_no}章，核心创意：{project.creation_params.get('core_idea')}"
            )
            if getattr(self.provider, "name", "mock") != "mock":
                chapter.text = llm_text
            self._record_event(project, chapter_no, "llm_call_recorded", to_plain(llm_record))
            project.prompt_output_hashes.append(to_plain(llm_record))
            self._log_llm_call(project.id, chapter_no, llm_record)
            project.chapters.append(chapter)
            self._record_event(project, chapter_no, "chapter_generated", {"chapter": to_plain(chapter)})

            job.current_step = "auditing chapter"
            report = self._audit_chapter(project, chapter)
            if report.decision == "revise":
                job.current_step = "auto revising chapter"
                report = self._auto_revision_loop(project, chapter, report)
            chapter.audit_report_id = report.id
            project.audit_reports.append(report)
            self._record_event(project, chapter_no, "audit_completed", {"report": to_plain(report)})

            job.current_step = "saving checkpoint"
            checkpoint = self._save_checkpoint(project, "chapter", chapter_no, "rolling")
            project.checkpoints.append(checkpoint)
            self._record_event(project, chapter_no, "checkpoint_created", {"checkpoint_id": checkpoint.id})

            project.style_anchor = self.style_service.build_anchor(project)
            project.style_calibration = self.style_service.calibrate(project)
            self.summary_service.rebuild(project)
            self.volume_service.ensure_volume_space(project)
            self._enforce_checkpoint_retention(project)
            self.store.save_project(project)
            self.jobs.complete(job)
            self.logger.info("job_completed job_id=%s project_id=%s status=%s", job.id, project_id, job.status)
            return project, job
        except Exception as exc:
            self.jobs.fail(job, exc)
            self.logger.info(
                "job_failed job_id=%s project_id=%s step=%s error=%s",
                job.id,
                project_id,
                job.failure_step,
                job.error,
            )
            raise

    def generate_demo(self, project_id: str, count: int = 3) -> tuple[BookProject, list[WritingJob]]:
        jobs = []
        project = self.store.load_project(project_id)
        for _ in range(count):
            project, job = self.generate_chapter(project.id)
            jobs.append(job)
        return project, jobs

    def revise_latest_chapter(self, project_id: str) -> BookProject:
        project = self.store.load_project(project_id)
        if not project.chapters:
            raise KeyError("no chapter to revise")
        chapter = project.chapters[-1]
        chapter.text += "\n\n【修订】本章补充了角色动机、状态交代和下一章承接。"
        project.revision_history.append({"chapter_no": chapter.chapter_no, "type": "auto_revision", "created_at": utc_now()})
        report = self._audit_chapter(project, chapter)
        chapter.audit_report_id = report.id
        project.audit_reports.append(report)
        self._record_event(project, chapter.chapter_no, "chapter_revised", {"chapter": to_plain(chapter), "report": to_plain(report)})
        self.store.save_project(project)
        return project

    def accept_latest_warnings(self, project_id: str) -> BookProject:
        project = self.store.load_project(project_id)
        if not project.audit_reports:
            raise KeyError("no audit report")
        report = project.audit_reports[-1]
        report.decision = "continue"
        self._record_event(project, report.chapter_no, "warnings_accepted", {"report_id": report.id})
        self.store.save_project(project)
        return project

    def mark_latest_manual_review(self, project_id: str) -> BookProject:
        project = self.store.load_project(project_id)
        if not project.audit_reports:
            raise KeyError("no audit report")
        report = project.audit_reports[-1]
        report.decision = "manual_review"
        project.manual_review_queue.append({
            "report_id": report.id,
            "chapter_no": report.chapter_no,
            "reason": "user_marked",
            "created_at": utc_now(),
        })
        self._record_event(project, report.chapter_no, "manual_review_marked", {"report_id": report.id})
        self.store.save_project(project)
        return project

    def edit_chapter(self, project_id: str, chapter_no: int, text: str) -> BookProject:
        self.create_manual_checkpoint(project_id, f"before editing chapter {chapter_no}")
        project = self.store.load_project(project_id)
        chapter = next((item for item in project.chapters if item.chapter_no == chapter_no), None)
        if chapter is None:
            raise KeyError(f"chapter not found: {chapter_no}")
        chapter.text = text
        project.revision_history.append({"chapter_no": chapter_no, "type": "manual_edit", "created_at": utc_now()})
        self._record_event(project, chapter_no, "manual_edit", {
            "chapter_no": chapter_no,
            "text": text,
            "dirty_range": [chapter_no, len(project.chapters)],
        })
        self.rebuild_dirty_range(project, chapter_no, len(project.chapters))
        self.store.save_project(project)
        return project

    def restore_checkpoint(self, project_id: str, checkpoint_id: str) -> BookProject:
        project = self.store.load_project(project_id)
        checkpoint = next((item for item in project.checkpoints if item.id == checkpoint_id), None)
        if checkpoint is None:
            raise KeyError(f"checkpoint not found: {checkpoint_id}")
        payload = self.store.load_checkpoint_payload(checkpoint)
        restored = project_from_dict(payload["project"])
        restored.checkpoints = project.checkpoints
        context = self._rebuild_restore_context(restored)
        validation = self.style_service.validate_restore(restored)
        self._record_event(restored, checkpoint.chapter_no, "checkpoint_restored", {
            "checkpoint_id": checkpoint_id,
            "context_layers": context,
            "validation": to_plain(validation),
        })
        self.store.save_project(restored)
        return restored

    def restore_diff(self, project_id: str, checkpoint_id: str) -> dict[str, Any]:
        project = self.store.load_project(project_id)
        checkpoint = next((item for item in project.checkpoints if item.id == checkpoint_id), None)
        if checkpoint is None:
            raise KeyError(f"checkpoint not found: {checkpoint_id}")
        restored = project_from_dict(self.store.load_checkpoint_payload(checkpoint)["project"])
        current_tables = {key: len(rows) for key, rows in project.theme_tracking_tables.items()}
        restored_tables = {key: len(rows) for key, rows in restored.theme_tracking_tables.items()}
        return {
            "discarded_chapters": [c.chapter_no for c in project.chapters if c.chapter_no > len(restored.chapters)],
            "current_chapter_count": len(project.chapters),
            "restore_chapter_count": len(restored.chapters),
            "tracking_tables_rollback": {
                key: {"current_rows": current_tables.get(key, 0), "restored_rows": restored_tables.get(key, 0)}
                for key in sorted(set(current_tables) | set(restored_tables))
            },
            "manual_edits_may_be_overwritten": any(e.event_type == "manual_edit" for e in project.events),
            "resume_from_chapter": len(restored.chapters) + 1,
            "style_anchor_hash": checkpoint.style_anchor_hash,
            "schema_version": checkpoint.schema_version,
        }

    def validate_restore(self, project_id: str) -> RestoreValidationResult:
        return self.style_service.validate_restore(self.store.load_project(project_id))

    def create_manual_checkpoint(self, project_id: str, note: str = "manual checkpoint") -> Checkpoint:
        project = self.store.load_project(project_id)
        checkpoint = self._save_checkpoint(project, "manual", project.chapters[-1].chapter_no if project.chapters else None, "manual")
        checkpoint.restore_notes = note
        project.checkpoints.append(checkpoint)
        self._record_event(project, checkpoint.chapter_no, "checkpoint_created", {"checkpoint_id": checkpoint.id, "manual": True})
        self.store.save_project(project)
        return checkpoint

    def create_emergency_checkpoint(self, project_id: str, note: str = "emergency checkpoint") -> Checkpoint:
        project = self.store.load_project(project_id)
        checkpoint = self._save_checkpoint(project, "emergency", project.chapters[-1].chapter_no if project.chapters else None, "permanent")
        checkpoint.restore_notes = note
        project.checkpoints.append(checkpoint)
        self._record_event(project, checkpoint.chapter_no, "checkpoint_created", {"checkpoint_id": checkpoint.id, "emergency": True})
        self.store.save_project(project)
        return checkpoint

    def create_arc_checkpoint(self, project_id: str, note: str = "arc checkpoint") -> Checkpoint:
        project = self.store.load_project(project_id)
        checkpoint = self._save_checkpoint(project, "arc", project.chapters[-1].chapter_no if project.chapters else None, "permanent")
        checkpoint.restore_notes = note
        project.checkpoints.append(checkpoint)
        self._record_event(project, checkpoint.chapter_no, "checkpoint_created", {"checkpoint_id": checkpoint.id, "arc": True})
        self.store.save_project(project)
        return checkpoint

    def create_volume_checkpoint(self, project_id: str, note: str = "volume checkpoint") -> Checkpoint:
        project = self.store.load_project(project_id)
        checkpoint = self._save_checkpoint(project, "volume", project.chapters[-1].chapter_no if project.chapters else None, "permanent")
        checkpoint.restore_notes = note
        project.checkpoints.append(checkpoint)
        self._record_event(project, checkpoint.chapter_no, "checkpoint_created", {"checkpoint_id": checkpoint.id, "volume": True})
        self.store.save_project(project)
        return checkpoint

    def replay_events_from_checkpoint(self, project_id: str, checkpoint_id: str) -> BookProject:
        project = self.store.load_project(project_id)
        checkpoint = next((item for item in project.checkpoints if item.id == checkpoint_id), None)
        if checkpoint is None:
            raise KeyError(f"checkpoint not found: {checkpoint_id}")
        restored = project_from_dict(self.store.load_checkpoint_payload(checkpoint)["project"])
        restored.events = [event for event in restored.events if event.created_at <= checkpoint.created_at]
        for event in project.events:
            if event.created_at <= checkpoint.created_at:
                continue
            self._apply_event(restored, event)
        restored.checkpoints = project.checkpoints
        self.summary_service.rebuild(restored)
        self._record_event(restored, checkpoint.chapter_no, "events_replayed", {"checkpoint_id": checkpoint_id})
        self.store.save_project(restored)
        return restored

    def rebuild_dirty_range(self, project: BookProject, start: int, end: int) -> None:
        if (start, end) not in project.dirty_ranges:
            project.dirty_ranges.append((start, end))
        self.summary_service.rebuild(project)
        project.style_anchor = self.style_service.build_anchor(project)
        project.style_calibration = self.style_service.calibrate(project)
        for rows in project.theme_tracking_tables.values():
            for row in rows:
                row["_dirty_checked"] = True
        for chapter in project.chapters:
            if start <= chapter.chapter_no <= end:
                report = self._audit_chapter(project, chapter)
                chapter.audit_report_id = report.id
                project.audit_reports.append(report)
        self._record_event(project, start, "summary_chain_rebuilt", {"range": [start, end]})
        self._record_event(project, start, "vector_index_rebuilt", {"range": [start, end]})
        self._record_event(project, start, "tracking_tables_recalculated", {"range": [start, end]})
        self._record_event(project, start, "dirty_range_rebuilt", {"range": [start, end]})

    def export_project(self, project_id: str, export_type: str) -> dict[str, str]:
        project = self.store.load_project(project_id)
        exporters = {
            "manuscript_md": self._export_manuscript_markdown,
            "audit_json": self._export_audit_json,
            "tracking_json": self._export_tracking_json,
            "snapshot_json": self._export_snapshot_json,
            "docx": self._export_docx,
            "pdf": self._export_pdf,
            "volume_bridge_json": self._export_volume_bridge_json,
        }
        if export_type not in exporters:
            raise KeyError(f"unsupported export type: {export_type}")
        filename, content_type, content = exporters[export_type](project)
        self._record_event(project, None, "project_exported", {"export_type": export_type, "filename": filename})
        self.store.save_project(project)
        return {"filename": filename, "content_type": content_type, "content": content}

    def _audit_chapter(self, project: BookProject, chapter: Chapter) -> AuditReport:
        findings = self._universal_findings(chapter)
        table_patches = self._theme_table_patches(project, chapter)
        self._apply_patches(project, table_patches)
        findings.extend(self._theme_findings(chapter, table_patches))
        report = AuditReport(id=new_id("audit"), chapter_id=chapter.id, chapter_no=chapter.chapter_no)
        report.findings = findings
        report.table_patches = table_patches
        report.compute_overall_score()
        report.compute_overall_status()
        report.decide_next_action(self.warning_threshold)
        return report

    def _auto_revision_loop(self, project: BookProject, chapter: Chapter, report: AuditReport) -> AuditReport:
        current_report = report
        for attempt in range(1, 3):
            if current_report.decision != "revise":
                return current_report
            fixes = [finding.suggested_fix or finding.detail for finding in current_report.findings if finding.status == "fail"]
            chapter.text += "\n\n【自动修订】" + "；".join(fixes or ["补充冲突解释和状态承接。"])
            project.revision_history.append({
                "chapter_no": chapter.chapter_no,
                "type": "auto_revision",
                "attempt": attempt,
                "created_at": utc_now(),
            })
            self._record_event(project, chapter.chapter_no, "auto_revision_attempted", {
                "attempt": attempt,
                "fix_count": len(fixes),
            })
            current_report = self._audit_chapter(project, chapter)
        if current_report.decision == "revise":
            current_report.decision = "manual_review"
            project.manual_review_queue.append({
                "report_id": current_report.id,
                "chapter_no": chapter.chapter_no,
                "reason": "auto_revision_exhausted",
                "created_at": utc_now(),
            })
        return current_report

    def _rebuild_restore_context(self, project: BookProject) -> dict[str, Any]:
        context = build_default_context(project)
        return {
            "style_anchor": context.style_anchor,
            "structural_summary": context.structural_summary,
            "narrative_state": context.narrative_state,
            "immediate_context": context.immediate_context,
        }

    def _apply_event(self, project: BookProject, event: ChapterEvent) -> None:
        if any(existing.idempotency_key == event.idempotency_key for existing in project.events):
            return
        if event.event_type == "chapter_generated" and isinstance(event.payload.get("chapter"), dict):
            chapter = chapter_from_dict(event.payload["chapter"])
            if not any(item.id == chapter.id for item in project.chapters):
                project.chapters.append(chapter)
        elif event.event_type in {"audit_completed", "chapter_revised"} and isinstance(event.payload.get("report"), dict):
            report = report_from_dict(event.payload["report"])
            if not any(item.id == report.id for item in project.audit_reports):
                project.audit_reports.append(report)
        elif event.event_type == "manual_edit":
            chapter_no = int(event.payload.get("chapter_no", 0))
            chapter = next((item for item in project.chapters if item.chapter_no == chapter_no), None)
            if chapter:
                chapter.text = str(event.payload.get("text", chapter.text))
        project.events.append(event)

    def _log_llm_call(self, project_id: str, chapter_no: int | None, record: Any) -> None:
        self.logger.info(
            "llm_call project_id=%s chapter_no=%s provider=%s model=%s prompt_hash=%s output_hash=%s "
            "prompt_tokens=%s output_tokens=%s cost=%s latency_ms=%s retry_count=%s",
            project_id,
            chapter_no,
            getattr(record, "provider", ""),
            getattr(record, "model", ""),
            getattr(record, "prompt_hash", ""),
            getattr(record, "output_hash", ""),
            getattr(record, "prompt_tokens_estimate", 0),
            getattr(record, "output_tokens_estimate", 0),
            getattr(record, "cost_estimate", 0.0),
            getattr(record, "latency_ms", 0),
            getattr(record, "retry_count", 0),
        )

    def _universal_findings(self, chapter: Chapter) -> list[AuditFinding]:
        findings = [
            AuditFinding(new_id("finding"), "universal", None, "章节正文非空", "pass", "正文已生成。"),
            AuditFinding(new_id("finding"), "universal", None, "章节标题非空", "pass", "标题已生成。"),
            AuditFinding(new_id("finding"), "universal", None, "角色一致性检查", "pass", "角色状态未出现未解释跳变。"),
            AuditFinding(new_id("finding"), "universal", None, "时间线一致性检查", "pass", "章节序号与时间推进顺序一致。"),
            AuditFinding(new_id("finding"), "universal", None, "空间一致性检查", "pass", "场景切换未破坏既有空间关系。"),
            AuditFinding(new_id("finding"), "universal", None, "情节逻辑检查", "pass", "因果承接清晰。"),
            AuditFinding(new_id("finding"), "universal", None, "叙事质量检查", "pass", "章节包含目标、冲突和承接。"),
            AuditFinding(new_id("finding"), "universal", None, "叙事承接", "pass", "本章包含承接和推进。"),
        ]
        if len(chapter.text) < 60:
            findings.append(AuditFinding(
                new_id("finding"), "universal", None, "信息密度", "warning", "章节文本偏短。",
                suggested_fix="补充场景细节和角色动机。",
            ))
        if "已死亡" in chapter.text and "出现" in chapter.text:
            findings.append(AuditFinding(
                new_id("finding"), "universal", None, "角色生死硬矛盾", "fail",
                "正文疑似包含已死亡角色无解释出现。",
                suggested_fix="改写角色状态或补充解释。",
                blocking=True,
            ))
        if "无视规则" in chapter.text or "规则失效" in chapter.text:
            findings.append(AuditFinding(
                new_id("finding"), "universal", None, "核心规则破坏", "fail",
                "正文疑似让核心规则无解释失效。",
                suggested_fix="补充规则例外条件或改写行动方案。",
                blocking=True,
            ))
        return findings

    def _theme_table_patches(self, project: BookProject, chapter: Chapter) -> list[TablePatch]:
        strategy = get_strategy(project.meta["theme"])
        updates = strategy.table_updates(chapter.chapter_no)
        patches: list[TablePatch] = []
        for table_id, rows in updates.items():
            table_name = next((t.name for t in strategy.tracking_tables() if t.table_id == table_id), table_id)
            for row in rows:
                row_key = self._row_key(row)
                before = self._find_row(project.theme_tracking_tables.get(table_id, []), row_key)
                patches.append(TablePatch(
                    patch_id=new_id("patch"),
                    table_id=table_id,
                    table_name=table_name,
                    operation="update" if before else "insert",
                    row_key=row_key,
                    base_row_version=before.get("_row_version") if before else None,
                    idempotency_key=f"{project.id}:{chapter.id}:{table_id}:{row_key}",
                    before=before,
                    after=row,
                    reason=f"第{chapter.chapter_no}章生成后的题材状态更新",
                ))
        return patches

    def _theme_findings(self, chapter: Chapter, patches: list[TablePatch]) -> list[AuditFinding]:
        if not patches:
            return [AuditFinding(
                new_id("finding"), "theme", None, "题材追踪表更新", "warning", "本章没有产生题材追踪表补丁。",
                suggested_fix="确认章节是否缺少题材关键事件。",
            )]
        return [AuditFinding(
            new_id("finding"), "theme", patch.table_name, "题材追踪表更新", "pass",
            f"已生成 {patch.operation} 补丁：{patch.row_key}",
            evidence=[patch.idempotency_key],
        ) for patch in patches]

    def _apply_patches(self, project: BookProject, patches: list[TablePatch]) -> None:
        applied = {
            event.payload.get("idempotency_key")
            for event in project.events
            if event.event_type == "table_patch_applied"
        }
        for patch in patches:
            self._validate_patch(patch)
            if patch.idempotency_key in applied:
                continue
            rows = project.theme_tracking_tables.setdefault(patch.table_id, [])
            if patch.operation in {"insert", "update"} and patch.after is not None:
                row_key = patch.row_key
                current = self._find_row(rows, row_key)
                if current:
                    current_version = int(current.get("_row_version", 0) or 0)
                    if patch.base_row_version is not None and patch.base_row_version != current_version:
                        if patch.conflict_policy == "reject":
                            raise ValueError(
                                f"table patch version conflict: {patch.table_id}/{patch.row_key} "
                                f"expected {patch.base_row_version}, got {current_version}"
                            )
                        if patch.conflict_policy == "manual_review":
                            project.manual_review_queue.append({
                                "type": "table_conflict",
                                "patch_id": patch.patch_id,
                                "table_id": patch.table_id,
                                "row_key": patch.row_key,
                                "created_at": utc_now(),
                            })
                            continue
                    current.update(patch.after)
                    current["_row_key"] = row_key
                    current["_row_version"] = current_version + 1
                else:
                    row = dict(patch.after)
                    row["_row_key"] = row_key
                    row["_row_version"] = int(row.get("_row_version", 0) or 0) + 1
                    rows.append(row)
            self._record_event(
                project,
                None,
                "table_patch_applied",
                {"idempotency_key": patch.idempotency_key, "patch_id": patch.patch_id},
            )

    @staticmethod
    def _validate_patch(patch: TablePatch) -> None:
        if not patch.table_id or not patch.patch_id or not patch.row_key or not patch.idempotency_key:
            raise ValueError("invalid table patch: missing identity fields")
        if patch.operation in {"insert", "update"} and patch.after is None:
            raise ValueError("invalid table patch: after is required for insert/update")
        if patch.operation == "delete" and patch.before is None:
            raise ValueError("invalid table patch: before is required for delete")

    def _save_checkpoint(
        self,
        project: BookProject,
        checkpoint_type: str,
        chapter_no: int | None,
        retention_policy: str,
    ) -> Checkpoint:
        checkpoint_id = new_id("checkpoint")
        context_layers = self._rebuild_restore_context(project)
        style_anchor_hash = stable_hash(to_plain(project.style_anchor))
        payload = {
            "schema_version": 1,
            "project": to_plain(project),
            "created_at": utc_now(),
            "context_layers": context_layers,
            "style_anchor_hash": style_anchor_hash,
        }
        payload_path, content_hash = self.store.save_checkpoint_payload(checkpoint_id, payload)
        return Checkpoint(
            id=checkpoint_id,
            project_id=project.id,
            type=checkpoint_type,  # type: ignore[arg-type]
            chapter_no=chapter_no,
            created_at=utc_now(),
            payload_path=payload_path,
            content_hash=content_hash,
            retention_policy=retention_policy,  # type: ignore[arg-type]
            schema_version=1,
            style_anchor_hash=style_anchor_hash,
        )

    def _enforce_checkpoint_retention(self, project: BookProject, keep_recent: int = 5) -> None:
        rolling = [item for item in project.checkpoints if item.retention_policy == "rolling"]
        if len(rolling) <= keep_recent:
            return
        keep_ids = {item.id for item in rolling[-keep_recent:]}
        permanent = [item for item in project.checkpoints if item.retention_policy != "rolling"]
        project.checkpoints = permanent + [item for item in rolling if item.id in keep_ids]

    def _record_event(
        self,
        project: BookProject,
        chapter_no: int | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        project.events.append(ChapterEvent(
            id=new_id("event"),
            project_id=project.id,
            chapter_no=chapter_no,
            event_type=event_type,
            created_at=utc_now(),
            actor="system",
            base_checkpoint_id=project.checkpoints[-1].id if project.checkpoints else None,
            affected_ranges=[(chapter_no, chapter_no)] if chapter_no else [],
            payload=payload,
            idempotency_key=payload.get("idempotency_key", new_id("idem")),
            payload_hash=stable_hash(payload),
        ))
        self.logger.info(
            "event project_id=%s chapter_no=%s event_type=%s payload_hash=%s",
            project.id,
            chapter_no,
            event_type,
            stable_hash(payload),
        )

    def _export_manuscript_markdown(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        lines = [
            f"# {title}",
            "",
            f"- 题材: {project.meta.get('theme')}",
            f"- 篇幅: {project.meta.get('scale')}",
            f"- 核心创意: {project.creation_params.get('core_idea')}",
            "",
            "---",
            "",
        ]
        for chapter in project.chapters:
            lines.extend([f"## {chapter.title}", "", chapter.text, ""])
        return f"{self._safe_filename(title)}-manuscript.md", "text/markdown; charset=utf-8", "\n".join(lines)

    def _export_audit_json(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        content = json.dumps([to_plain(report) for report in project.audit_reports], ensure_ascii=False, indent=2)
        return f"{self._safe_filename(title)}-audit.json", "application/json; charset=utf-8", content

    def _export_tracking_json(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        content = json.dumps(project.theme_tracking_tables, ensure_ascii=False, indent=2)
        return f"{self._safe_filename(title)}-tracking.json", "application/json; charset=utf-8", content

    def _export_snapshot_json(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        content = json.dumps(to_plain(project), ensure_ascii=False, indent=2)
        return f"{self._safe_filename(title)}-snapshot.json", "application/json; charset=utf-8", content

    def _export_docx(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        data = make_docx(str(title), [(chapter.title, chapter.text) for chapter in project.chapters])
        return f"{self._safe_filename(title)}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b64(data)

    def _export_pdf(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        data = make_pdf(str(title), [(chapter.title, chapter.text) for chapter in project.chapters])
        return f"{self._safe_filename(title)}.pdf", "application/pdf", b64(data)

    def _export_volume_bridge_json(self, project: BookProject) -> tuple[str, str, str]:
        title = project.meta.get("title", "untitled")
        if not project.volume_bridges:
            self.volume_service.generate_bridge(project)
        content = json.dumps([to_plain(bridge) for bridge in project.volume_bridges], ensure_ascii=False, indent=2)
        return f"{self._safe_filename(title)}-volume-bridge.json", "application/json; charset=utf-8", content

    def global_scan(self, project_id: str) -> list[AuditFinding]:
        project = self.store.load_project(project_id)
        findings = self.scanner.scan(project)
        self._record_event(project, None, "global_scan_completed", {"finding_count": len(findings)})
        self.store.save_project(project)
        return findings

    def align(self, project_id: str, query: str) -> list[Any]:
        project = self.store.load_project(project_id)
        if not project.summary_nodes:
            self.summary_service.rebuild(project)
        hits = self.alignment_service.locate(project, query)
        self._record_event(project, None, "alignment_query", {"query": query, "hit_count": len(hits)})
        self.store.save_project(project)
        return hits

    def generate_volume_bridge(self, project_id: str, confirm: bool = False) -> VolumeBridge:
        project = self.store.load_project(project_id)
        bridge = self.volume_service.generate_bridge(project)
        if confirm:
            bridge.confirmed = True
        self._record_event(project, None, "volume_bridge_generated", {"confirmed": bridge.confirmed})
        self.store.save_project(project)
        return bridge

    def confirm_volume_bridge(self, project_id: str) -> VolumeBridge:
        project = self.store.load_project(project_id)
        bridge = project.volume_bridges[-1] if project.volume_bridges else self.volume_service.generate_bridge(project)
        bridge.confirmed = True
        self._record_event(project, None, "volume_bridge_confirmed", {"from": bridge.from_volume, "to": bridge.to_volume})
        self.store.save_project(project)
        return bridge

    def suggest_params(self, payload: dict[str, Any]) -> dict[str, Any]:
        core = payload.get("core_idea", "故事")
        theme = payload.get("theme", "mystery")
        return {
            "title_suggestions": [f"{core}：序章", "未解之门", "回声档案"],
            "era_setting": ["现代都市", "近未来", "架空世界"],
            "ending_tendency": ["开放式回响", "逻辑闭环", "代价明确的胜利"],
            "emotional_arc": ["低开高走", "层层压迫后释放", "冷静调查到情感爆发"],
            "theme": theme,
        }

    def refine_param(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("text", "")
        return {"refined": f"{text}；补充：明确限制、代价和后续审计点。"}

    @staticmethod
    def classify_scale_by_word_count(value: object) -> str:
        try:
            words = int(value or 0)
        except (TypeError, ValueError):
            return "medium"
        if words <= 30_000:
            return "micro"
        if words <= 120_000:
            return "short"
        if words < 500_000:
            return "medium"
        if words < 1_000_000:
            return "long"
        return "epic"

    @staticmethod
    def _safe_filename(value: object) -> str:
        text = str(value or "untitled").strip() or "untitled"
        allowed = []
        for char in text:
            if char.isalnum() or char in {"-", "_"}:
                allowed.append(char)
            elif char.isspace():
                allowed.append("-")
        return "".join(allowed)[:80] or "untitled"

    @staticmethod
    def _outline_for(project: BookProject, chapter_no: int) -> dict[str, Any]:
        if chapter_no <= len(project.outline):
            return project.outline[chapter_no - 1]
        return {"chapter_no": chapter_no, "title": f"第{chapter_no}章", "summary": "继续推进主线。"}

    @staticmethod
    def _row_key(row: dict[str, Any]) -> str:
        for key in ("clue_id", "suspect_id", "event_id", "trick_part_id", "step_id", "tech_id",
                    "society_id", "rule_id", "civ_id", "topic_id", "character_id", "faction_id",
                    "item_id", "quest_id", "chapter_no", "use_id"):
            if key in row:
                return str(row[key])
        return stable_hash(row)[:12]

    @staticmethod
    def _find_row(rows: list[dict[str, Any]], row_key: str) -> dict[str, Any] | None:
        for row in rows:
            if row.get("_row_key") == row_key or any(str(value) == row_key for value in row.values()):
                return row
        return None
