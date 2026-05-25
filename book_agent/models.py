from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class CreationParams:
    title: str
    core_idea: str
    target_audience: str
    language_style: str
    narrative_pov: str
    tone: list[str]
    special_requirements: str = ""
    target_words: int | None = None
    scale: Literal["micro", "short", "medium", "long", "epic"] = "medium"


@dataclass
class WorldSetting:
    premise: str
    era: str
    locations: list[str]
    rules: list[str]
    forbidden_contradictions: list[str] = field(default_factory=list)


@dataclass
class Character:
    id: str
    name: str
    role: str
    status: Literal["active", "dead", "left", "sealed"] = "active"
    knowledge: list[str] = field(default_factory=list)
    voice_markers: list[str] = field(default_factory=list)


@dataclass
class PlotStructure:
    type: str
    current_stage: str
    stages: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ChapterOutline:
    chapter_no: int
    title: str
    summary: str
    target_words: int | None = None


@dataclass
class Chapter:
    id: str
    chapter_no: int
    title: str
    text: str
    outline_summary: str
    audit_report_id: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass
class Foreshadow:
    id: str
    type: str
    description: str
    planted_chapter: int
    planted_text: str
    intended_payoff: str
    payoff_chapter: int | None
    status: Literal["planted", "reinforced", "resolved", "abandoned"] = "planted"
    urgency: int = 3
    reinforcements: list[dict[str, Any]] = field(default_factory=list)
    resolution: dict[str, Any] | None = None
    cross_volume: bool = False
    related_foreshadows: list[str] = field(default_factory=list)


@dataclass
class AuditFinding:
    id: str
    scope: str
    table_name: str | None
    rule: str
    status: Literal["pass", "warning", "fail"]
    detail: str
    evidence: list[str] = field(default_factory=list)
    suggested_fix: str | None = None
    blocking: bool = False


@dataclass
class TablePatch:
    patch_id: str
    table_id: str
    table_name: str
    operation: Literal["insert", "update", "delete", "noop"]
    row_key: str
    base_row_version: int | None
    idempotency_key: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str
    conflict_policy: Literal["reject", "merge", "manual_review"] = "reject"


@dataclass
class TableAuditResult:
    table_id: str
    findings: list[AuditFinding]
    table_patches: list[TablePatch]
    summary: str
    raw_output_hash: str


@dataclass
class AuditReport:
    id: str
    chapter_id: str
    chapter_no: int
    findings: list[AuditFinding] = field(default_factory=list)
    table_patches: list[TablePatch] = field(default_factory=list)
    score: float = 0.0
    overall_status: Literal["pass", "warning", "fail"] = "pass"
    decision: Literal["continue", "revise", "manual_review"] = "continue"
    warning_count: int = 0
    fail_count: int = 0
    created_at: str = field(default_factory=utc_now)

    def has_blocking_fail(self) -> bool:
        return any(f.status == "fail" and f.blocking for f in self.findings)

    def compute_overall_score(self) -> None:
        weights = {"pass": 1.0, "warning": 0.6, "fail": 0.0}
        self.score = sum(weights[f.status] for f in self.findings) / max(len(self.findings), 1)

    def compute_overall_status(self) -> None:
        self.warning_count = sum(1 for f in self.findings if f.status == "warning")
        self.fail_count = sum(1 for f in self.findings if f.status == "fail")
        if self.has_blocking_fail() or self.fail_count > 0:
            self.overall_status = "fail"
        elif self.warning_count > 0:
            self.overall_status = "warning"
        else:
            self.overall_status = "pass"

    def decide_next_action(self, warning_threshold: int = 3) -> None:
        if self.has_blocking_fail() or self.overall_status == "fail":
            self.decision = "revise"
        elif self.overall_status == "warning" and self.warning_count > warning_threshold:
            self.decision = "manual_review"
        else:
            self.decision = "continue"


@dataclass
class Checkpoint:
    id: str
    project_id: str
    type: Literal["chapter", "arc", "volume", "manual", "emergency"]
    chapter_no: int | None
    created_at: str
    payload_path: str
    content_hash: str
    retention_policy: Literal["rolling", "permanent", "manual"]
    schema_version: int = 1
    style_anchor_hash: str | None = None
    restore_notes: str | None = None


@dataclass
class ChapterEvent:
    id: str
    project_id: str
    chapter_no: int | None
    event_type: str
    created_at: str
    actor: Literal["system", "user", "llm", "migration"]
    base_checkpoint_id: str | None
    affected_ranges: list[tuple[int, int]]
    payload: dict[str, Any]
    idempotency_key: str
    payload_hash: str


@dataclass
class WritingJob:
    id: str
    project_id: str
    type: str
    status: Literal["queued", "running", "paused", "cancelled", "failed", "completed"]
    progress: float
    current_step: str
    idempotency_key: str
    retry_count: int = 0
    error: str | None = None
    failure_step: str | None = None
    can_retry: bool = True
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class WritingContext:
    style_anchor: dict[str, Any]
    structural_summary: dict[str, Any]
    narrative_state: dict[str, Any]
    immediate_context: dict[str, Any]


@dataclass
class StyleAnchor:
    narrative_pov: str
    tone_keywords: list[str]
    diction_notes: list[str]
    pacing_profile: dict[str, Any]
    dialogue_rules: dict[str, Any]
    sample_passages: list[str]
    forbidden_style_drifts: list[str] = field(default_factory=list)


@dataclass
class StyleCalibrationProfile:
    sample_chapter_ids: list[str]
    avg_sentence_length: tuple[float, float]
    paragraph_length_range: tuple[int, int]
    dialogue_ratio_range: tuple[float, float]
    pov_markers: list[str]
    character_voice_markers: dict[str, list[str]]
    forbidden_markers: list[str]


@dataclass
class RestoreValidationResult:
    style_score: float
    continuity_score: float
    theme_score: float
    issues: list[str]
    decision: Literal["ready", "manual_confirm", "rebuild_context", "manual_review"]


@dataclass
class SummaryNode:
    id: str
    level: Literal["book", "volume", "arc", "chapter", "scene"]
    parent_id: str | None
    chapter_range: tuple[int, int]
    summary: str
    entities: list[str]
    state_changes: list[dict[str, Any]]
    foreshadow_refs: list[str]
    table_patch_refs: list[str]
    source_refs: list[str]
    embedding_id: str


@dataclass
class AlignmentHit:
    source: Literal["vector", "structured", "summary_chain"]
    chapter_no: int | None
    entity_id: str | None
    evidence: str
    confidence: float
    freshness: Literal["current_volume", "previous_volume", "global"]
    payload: dict[str, Any]


@dataclass
class VolumeMemorySpace:
    volume_no: int
    volume_title: str
    chapter_range: tuple[int, int]
    local_vector_namespace: str
    local_tracking_tables: dict[str, list[dict[str, Any]]]
    local_character_states: dict[str, dict[str, Any]]
    local_plot_threads: list[dict[str, Any]]
    local_style_notes: dict[str, Any]
    sealed: bool = False


@dataclass
class VolumeBridge:
    from_volume: int
    to_volume: int
    bridge_version: str
    volume_resolution: str
    active_characters: list[dict[str, Any]]
    removed_characters: list[dict[str, Any]]
    unresolved_threads: list[dict[str, Any]]
    cross_volume_foreshadows: list[dict[str, Any]]
    global_rule_updates: list[dict[str, Any]]
    item_transfers: list[dict[str, Any]]
    relationship_changes: list[dict[str, Any]]
    style_anchor_delta: dict[str, Any]
    forbidden_contradictions: list[str]
    next_volume_hooks: list[str]
    confirmed: bool = False


@dataclass
class BookProject:
    id: str
    meta: dict[str, Any]
    creation_params: dict[str, Any]
    world_setting: dict[str, Any]
    characters: list[dict[str, Any]]
    plot_structure: dict[str, Any]
    outline: list[dict[str, Any]]
    chapters: list[Chapter] = field(default_factory=list)
    foreshadowing_registry: list[dict[str, Any]] = field(default_factory=list)
    theme_tracking_tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    audit_reports: list[AuditReport] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    events: list[ChapterEvent] = field(default_factory=list)
    summary_nodes: list[SummaryNode] = field(default_factory=list)
    volume_spaces: list[VolumeMemorySpace] = field(default_factory=list)
    volume_bridges: list[VolumeBridge] = field(default_factory=list)
    style_anchor: StyleAnchor | None = None
    style_calibration: StyleCalibrationProfile | None = None
    revision_history: list[dict[str, Any]] = field(default_factory=list)
    manual_review_queue: list[dict[str, Any]] = field(default_factory=list)
    dirty_ranges: list[tuple[int, int]] = field(default_factory=list)
    prompt_output_hashes: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
