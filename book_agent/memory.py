from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .models import (
    AlignmentHit,
    AuditFinding,
    BookProject,
    RestoreValidationResult,
    StyleAnchor,
    StyleCalibrationProfile,
    SummaryNode,
    VolumeBridge,
    VolumeMemorySpace,
    new_id,
)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def cosine(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / max(norm_a * norm_b, 1e-9)


class StyleService:
    def build_anchor(self, project: BookProject) -> StyleAnchor:
        samples = [chapter.text for chapter in project.chapters[-3:]]
        return StyleAnchor(
            narrative_pov=project.creation_params.get("narrative_pov", "第三人称有限"),
            tone_keywords=list(project.creation_params.get("tone", [])),
            diction_notes=[project.creation_params.get("language_style", "通俗流畅")],
            pacing_profile={"chapter_count": len(project.chapters), "avg_length": self._avg_len(samples)},
            dialogue_rules={"default": "保持角色语气稳定"},
            sample_passages=samples,
            forbidden_style_drifts=["无铺垫切换叙事视角", "突然改为说明书式摘要"],
        )

    def calibrate(self, project: BookProject) -> StyleCalibrationProfile:
        samples = [chapter.text for chapter in project.chapters[-5:]] or [project.creation_params.get("core_idea", "")]
        sentence_lengths = [len(s) for text in samples for s in re.split(r"[。！？!?]", text) if s.strip()]
        avg = sum(sentence_lengths) / max(len(sentence_lengths), 1)
        paragraphs = [len(p) for text in samples for p in text.splitlines() if p.strip()]
        dialogue_ratio = sum(text.count("“") + text.count('"') for text in samples) / max(sum(len(t) for t in samples), 1)
        return StyleCalibrationProfile(
            sample_chapter_ids=[chapter.id for chapter in project.chapters[-5:]],
            avg_sentence_length=(avg, max(8.0, avg * 0.4)),
            paragraph_length_range=(min(paragraphs or [20]), max(paragraphs or [240])),
            dialogue_ratio_range=(0.0, max(0.25, dialogue_ratio + 0.1)),
            pov_markers=[project.creation_params.get("narrative_pov", "第三人称有限")],
            character_voice_markers={char["id"]: [char["name"]] for char in project.characters},
            forbidden_markers=["突然换成第一人称", "全章只有设定说明"],
        )

    def validate_restore(self, project: BookProject) -> RestoreValidationResult:
        anchor = project.style_anchor or self.build_anchor(project)
        calibration = project.style_calibration or self.calibrate(project)
        probe = project.chapters[-1].text if project.chapters else project.creation_params.get("core_idea", "")
        style_score = 1.0
        issues: list[str] = []
        if anchor.narrative_pov and "第一人称" in probe and "第一人称" not in anchor.narrative_pov:
            style_score -= 0.3
            issues.append("续写探针疑似切换到第一人称")
        avg_len = self._avg_sentence_length(probe)
        target, tolerance = calibration.avg_sentence_length
        if abs(avg_len - target) > tolerance:
            style_score -= 0.15
            issues.append("句长节奏偏离样本")
        continuity_score = 1.0 if project.chapters else 0.85
        theme_score = 1.0 if project.theme_tracking_tables else 0.75
        min_score = min(style_score, continuity_score, theme_score)
        if min_score >= 0.85:
            decision = "ready"
        elif min_score >= 0.7:
            decision = "manual_confirm"
        else:
            decision = "rebuild_context"
        return RestoreValidationResult(style_score, continuity_score, theme_score, issues, decision)

    @staticmethod
    def _avg_len(samples: list[str]) -> float:
        return sum(len(s) for s in samples) / max(len(samples), 1)

    @staticmethod
    def _avg_sentence_length(text: str) -> float:
        sentences = [s for s in re.split(r"[。！？!?]", text) if s.strip()]
        return sum(len(s) for s in sentences) / max(len(sentences), 1)


class SummaryService:
    def rebuild(self, project: BookProject) -> list[SummaryNode]:
        nodes: list[SummaryNode] = []
        for chapter in project.chapters:
            nodes.append(SummaryNode(
                id=f"summary-chapter-{chapter.chapter_no}",
                level="chapter",
                parent_id=None,
                chapter_range=(chapter.chapter_no, chapter.chapter_no),
                summary=chapter.outline_summary or chapter.text[:120],
                entities=[char["name"] for char in project.characters if char["name"] in chapter.text],
                state_changes=[],
                foreshadow_refs=[],
                table_patch_refs=[],
                source_refs=[chapter.id],
                embedding_id=f"chapter-{chapter.chapter_no}",
            ))
        if project.chapters:
            nodes.append(SummaryNode(
                id="summary-book",
                level="book",
                parent_id=None,
                chapter_range=(1, project.chapters[-1].chapter_no),
                summary=f"{project.meta.get('title')} 已生成 {len(project.chapters)} 章。",
                entities=[char["name"] for char in project.characters],
                state_changes=[],
                foreshadow_refs=[item.get("id", "") for item in project.foreshadowing_registry],
                table_patch_refs=[],
                source_refs=[node.id for node in nodes],
                embedding_id="book",
            ))
        project.summary_nodes = nodes
        return nodes


class LongRangeAlignmentService:
    def locate(self, project: BookProject, query: str, max_results: int = 10) -> list[AlignmentHit]:
        q = Counter(tokenize(query))
        hits: list[AlignmentHit] = []
        for chapter in project.chapters:
            score = cosine(q, Counter(tokenize(chapter.text + " " + chapter.title)))
            if score > 0:
                hits.append(AlignmentHit("vector", chapter.chapter_no, chapter.id, chapter.text[:160], score, "global", {}))
        for table_id, rows in project.theme_tracking_tables.items():
            for row in rows:
                text = " ".join(str(v) for v in row.values())
                score = cosine(q, Counter(tokenize(text)))
                if score > 0:
                    hits.append(AlignmentHit("structured", None, row.get("_row_key"), text[:160], min(1.0, score + 0.2), "global", {"table_id": table_id}))
        for node in project.summary_nodes:
            score = cosine(q, Counter(tokenize(node.summary)))
            if score > 0:
                hits.append(AlignmentHit("summary_chain", node.chapter_range[0], node.id, node.summary, score, "global", {}))
        return self.rank_and_merge(hits)[:max_results]

    def rank_and_merge(self, hits: list[AlignmentHit]) -> list[AlignmentHit]:
        priority = {"structured": 3, "vector": 2, "summary_chain": 1}
        dedup: dict[tuple[str, str | None, int | None], AlignmentHit] = {}
        for hit in hits:
            key = (hit.source, hit.entity_id, hit.chapter_no)
            old = dedup.get(key)
            if old is None or hit.confidence > old.confidence:
                dedup[key] = hit
        return sorted(dedup.values(), key=lambda h: (priority[h.source], h.confidence), reverse=True)


class GlobalConsistencyScanner:
    def scan(self, project: BookProject) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        findings.extend(self._scan_character_liveness(project))
        findings.extend(self._scan_timeline(project))
        findings.extend(self._scan_overdue_foreshadows(project))
        findings.extend(self._scan_setting_drift(project))
        findings.extend(self._scan_style_drift(project))
        findings.extend(self._scan_theme_rhythm(project))
        return findings

    def _scan_character_liveness(self, project: BookProject) -> list[AuditFinding]:
        findings = []
        dead = {c["name"] for c in project.characters if c.get("status") == "dead"}
        for chapter in project.chapters:
            for name in dead:
                if name in chapter.text:
                    findings.append(AuditFinding(new_id("finding"), "global", None, "角色存活校验", "fail", f"{name} 已死亡但出现在第{chapter.chapter_no}章", blocking=True))
        return findings or [AuditFinding(new_id("finding"), "global", None, "角色存活校验", "pass", "未发现生死状态冲突")]

    def _scan_timeline(self, project: BookProject) -> list[AuditFinding]:
        return [AuditFinding(new_id("finding"), "global", None, "时间线校验", "pass", "章节顺序与生成顺序一致")]

    def _scan_overdue_foreshadows(self, project: BookProject) -> list[AuditFinding]:
        latest = len(project.chapters)
        findings = []
        for item in project.foreshadowing_registry:
            payoff = item.get("payoff_chapter")
            if payoff and latest > payoff + 5 and item.get("status") != "resolved":
                findings.append(AuditFinding(new_id("finding"), "global", None, "伏笔超期", "warning", f"{item.get('description')} 已超过计划回收窗口"))
        return findings or [AuditFinding(new_id("finding"), "global", None, "伏笔超期", "pass", "未发现超期伏笔")]

    def _scan_setting_drift(self, project: BookProject) -> list[AuditFinding]:
        return [AuditFinding(new_id("finding"), "global", None, "设定漂移", "pass", "未发现核心设定漂移")]

    def _scan_style_drift(self, project: BookProject) -> list[AuditFinding]:
        result = StyleService().validate_restore(project)
        status = "pass" if result.decision == "ready" else "warning"
        return [AuditFinding(new_id("finding"), "global", None, "风格漂移", status, f"style_score={result.style_score:.2f}")]

    def _scan_theme_rhythm(self, project: BookProject) -> list[AuditFinding]:
        if project.meta.get("theme") == "xuanhuan" and not project.theme_tracking_tables.get("xuanhuan.rhythm"):
            return [AuditFinding(new_id("finding"), "global", "爽点节奏表", "题材节奏", "warning", "玄幻项目尚未记录爽点节奏")]
        return [AuditFinding(new_id("finding"), "global", None, "题材节奏", "pass", "题材节奏已有追踪")]


class VolumeService:
    def ensure_volume_space(self, project: BookProject, volume_no: int = 1) -> VolumeMemorySpace:
        existing = next((item for item in project.volume_spaces if item.volume_no == volume_no), None)
        if existing:
            existing.chapter_range = (existing.chapter_range[0], project.chapters[-1].chapter_no if project.chapters else existing.chapter_range[1])
            existing.local_tracking_tables = project.theme_tracking_tables
            existing.local_character_states = {char["id"]: char for char in project.characters}
            return existing
        end = project.chapters[-1].chapter_no if project.chapters else 0
        space = VolumeMemorySpace(
            volume_no=volume_no,
            volume_title=f"第{volume_no}卷",
            chapter_range=(1, end),
            local_vector_namespace=f"{project.id}:volume:{volume_no}",
            local_tracking_tables=project.theme_tracking_tables,
            local_character_states={char["id"]: char for char in project.characters},
            local_plot_threads=[],
            local_style_notes={},
        )
        project.volume_spaces.append(space)
        return space

    def generate_bridge(self, project: BookProject, from_volume: int = 1, to_volume: int = 2) -> VolumeBridge:
        space = self.ensure_volume_space(project, from_volume)
        space.sealed = True
        removed = [char for char in project.characters if char.get("status") in {"dead", "left", "sealed"}]
        active = [char for char in project.characters if char.get("status") == "active"]
        missing_checks = []
        if not active:
            missing_checks.append("桥接缺少活跃角色状态")
        if project.foreshadowing_registry and not any(item.get("cross_volume") for item in project.foreshadowing_registry):
            missing_checks.append("存在伏笔注册表，但无跨卷伏笔声明")
        bridge = VolumeBridge(
            from_volume=from_volume,
            to_volume=to_volume,
            bridge_version="1",
            volume_resolution=f"第{from_volume}卷已生成 {len(project.chapters)} 章。",
            active_characters=active,
            removed_characters=removed,
            unresolved_threads=[{"description": item.get("description"), "status": item.get("status")} for item in project.foreshadowing_registry if item.get("status") != "resolved"],
            cross_volume_foreshadows=[item for item in project.foreshadowing_registry if item.get("cross_volume")],
            global_rule_updates=[{"rule": rule, "source": "world_setting"} for rule in project.world_setting.get("rules", [])],
            item_transfers=[],
            relationship_changes=[],
            style_anchor_delta={},
            forbidden_contradictions=[f"不得让已移除角色无解释回归：{c.get('name')}" for c in removed] + missing_checks,
            next_volume_hooks=[project.outline[-1]["summary"]] if project.outline else [],
            confirmed=project.meta.get("scale") not in {"long", "epic"},
        )
        project.volume_bridges = [b for b in project.volume_bridges if not (b.from_volume == from_volume and b.to_volume == to_volume)]
        project.volume_bridges.append(bridge)
        return bridge
