from __future__ import annotations

from book_agent.services import BookAgentService
from book_agent.storage import JsonStore
from book_agent.providers import MockLLMProvider


def test_create_project_and_generate_three_chapters(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({
        "title": "测试书",
        "theme": "mystery",
        "scale": "medium",
        "core_idea": "一个密室案件隐藏着时间差线索",
    })

    project, jobs = service.generate_demo(project.id, count=3)

    assert len(jobs) == 3
    assert all(job.status == "completed" for job in jobs)
    assert len(project.chapters) == 3
    assert len(project.audit_reports) == 3
    assert project.audit_reports[-1].overall_status in {"pass", "warning"}
    assert project.theme_tracking_tables["mystery.clues"]
    assert project.checkpoints


def test_tracking_patch_is_idempotent(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "测试书", "theme": "xuanhuan", "core_idea": "主角稳步修炼"})
    project, _job = service.generate_chapter(project.id)
    report = project.audit_reports[-1]
    rows_before = {
        table_id: len(rows)
        for table_id, rows in project.theme_tracking_tables.items()
    }

    service._apply_patches(project, report.table_patches)

    rows_after = {
        table_id: len(rows)
        for table_id, rows in project.theme_tracking_tables.items()
    }
    assert rows_after == rows_before


def test_restore_checkpoint_preserves_recoverable_state(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "测试书", "theme": "sci_fi", "core_idea": "一项技术改变社会"})
    project, _job = service.generate_chapter(project.id)
    checkpoint_id = project.checkpoints[-1].id
    project, _job = service.generate_chapter(project.id)
    assert len(project.chapters) == 2

    restored = service.restore_checkpoint(project.id, checkpoint_id)

    assert len(restored.chapters) == 1
    assert restored.chapters[0].chapter_no == 1
    assert restored.checkpoints
    assert restored.events[-1].event_type == "checkpoint_restored"


def test_export_manuscript_and_tracking(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "导出测试", "theme": "mystery", "core_idea": "导出草稿"})
    project, _job = service.generate_chapter(project.id)

    manuscript = service.export_project(project.id, "manuscript_md")
    tracking = service.export_project(project.id, "tracking_json")

    assert manuscript["filename"].endswith("-manuscript.md")
    assert "# 导出测试" in manuscript["content"]
    assert "## 第1章 新的证词" in manuscript["content"]
    assert tracking["filename"].endswith("-tracking.json")
    assert "mystery.clues" in tracking["content"]


def test_param_suggestions_and_refinement(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))

    suggestions = service.suggest_params({"core_idea": "时间差案件", "theme": "mystery"})
    refined = service.refine_param({"text": "密室诡计"})

    assert suggestions["title_suggestions"]
    assert suggestions["theme"] == "mystery"
    assert "限制" in refined["refined"]


def test_mock_llm_provider_records_calls():
    provider = MockLLMProvider()

    text, record = provider.generate_text("写一段测试文本")
    structured, structured_record = provider.generate_structured("输出 JSON")

    assert text
    assert record.provider == "mock"
    assert record.prompt_hash
    assert structured["status"] == "pass"
    assert structured_record.output_hash


def test_job_pause_cancel_retry_and_lock(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "任务测试", "theme": "mystery"})
    job = service.jobs.start(project.id, "generate_chapter", "running")

    try:
        service.jobs.start(project.id, "generate_chapter", "blocked")
        raise AssertionError("expected project write lock")
    except RuntimeError:
        pass

    assert service.jobs.pause(job.id).status == "paused"
    assert service.jobs.resume(job.id).status == "queued"
    assert service.jobs.cancel(job.id).status == "cancelled"
    retried = service.jobs.retry(job.id)
    assert retried.status == "queued"
    assert retried.retry_count == 1


def test_manual_edit_dirty_range_and_event_replay(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "编辑测试", "theme": "sci_fi", "core_idea": "技术边界"})
    project, _jobs = service.generate_demo(project.id, count=2)
    checkpoint_id = project.checkpoints[0].id

    edited = service.edit_chapter(project.id, 1, "改写后的第一章，明确技术限制。")
    replayed = service.replay_events_from_checkpoint(project.id, checkpoint_id)

    assert any(event.event_type == "manual_edit" for event in edited.events)
    assert any(event.event_type == "dirty_range_rebuilt" for event in edited.events)
    assert any(event.event_type == "events_replayed" for event in replayed.events)


def test_restore_diff_validation_scan_alignment_and_bridge(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "长篇测试", "theme": "xuanhuan", "scale": "epic", "core_idea": "主角修炼"})
    project, _jobs = service.generate_demo(project.id, count=3)
    checkpoint_id = project.checkpoints[0].id

    diff = service.restore_diff(project.id, checkpoint_id)
    validation = service.validate_restore(project.id)
    findings = service.global_scan(project.id)
    hits = service.align(project.id, "主角 修炼")
    bridge = service.generate_volume_bridge(project.id)
    confirmed = service.confirm_volume_bridge(project.id)

    assert diff["resume_from_chapter"] >= 2
    assert validation.decision in {"ready", "manual_confirm", "rebuild_context", "manual_review"}
    assert findings
    assert hits
    assert bridge.confirmed is False
    assert confirmed.confirmed is True


def test_docx_pdf_and_volume_bridge_exports(tmp_path):
    service = BookAgentService(JsonStore(tmp_path))
    project = service.create_project({"title": "格式导出", "theme": "mystery", "core_idea": "格式测试"})
    project, _job = service.generate_chapter(project.id)
    service.generate_volume_bridge(project.id, confirm=True)

    docx = service.export_project(project.id, "docx")
    pdf = service.export_project(project.id, "pdf")
    bridge = service.export_project(project.id, "volume_bridge_json")

    assert docx["filename"].endswith(".docx")
    assert docx["content_type"].startswith("application/vnd.openxmlformats")
    assert pdf["filename"].endswith(".pdf")
    assert pdf["content_type"] == "application/pdf"
    assert "volume_resolution" in bridge["content"]
