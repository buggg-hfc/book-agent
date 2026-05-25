from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .models import (
    AuditFinding,
    AuditReport,
    BookProject,
    Chapter,
    ChapterEvent,
    Checkpoint,
    StyleAnchor,
    StyleCalibrationProfile,
    SummaryNode,
    TablePatch,
    VolumeBridge,
    VolumeMemorySpace,
)


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_plain(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    return value


def chapter_from_dict(data: dict[str, Any]) -> Chapter:
    return Chapter(**data)


def finding_from_dict(data: dict[str, Any]) -> AuditFinding:
    return AuditFinding(**data)


def patch_from_dict(data: dict[str, Any]) -> TablePatch:
    return TablePatch(**data)


def report_from_dict(data: dict[str, Any]) -> AuditReport:
    data = dict(data)
    data["findings"] = [finding_from_dict(item) for item in data.get("findings", [])]
    data["table_patches"] = [patch_from_dict(item) for item in data.get("table_patches", [])]
    return AuditReport(**data)


def checkpoint_from_dict(data: dict[str, Any]) -> Checkpoint:
    data = dict(data)
    data.setdefault("schema_version", 1)
    data.setdefault("style_anchor_hash", None)
    return Checkpoint(**data)


def event_from_dict(data: dict[str, Any]) -> ChapterEvent:
    data = dict(data)
    data["affected_ranges"] = [tuple(item) for item in data.get("affected_ranges", [])]
    return ChapterEvent(**data)


def summary_node_from_dict(data: dict[str, Any]) -> SummaryNode:
    data = dict(data)
    data["chapter_range"] = tuple(data["chapter_range"])
    return SummaryNode(**data)


def volume_space_from_dict(data: dict[str, Any]) -> VolumeMemorySpace:
    data = dict(data)
    data["chapter_range"] = tuple(data["chapter_range"])
    return VolumeMemorySpace(**data)


def volume_bridge_from_dict(data: dict[str, Any]) -> VolumeBridge:
    return VolumeBridge(**data)


def project_from_dict(data: dict[str, Any]) -> BookProject:
    data = dict(data)
    data["chapters"] = [chapter_from_dict(item) for item in data.get("chapters", [])]
    data["audit_reports"] = [report_from_dict(item) for item in data.get("audit_reports", [])]
    data["checkpoints"] = [checkpoint_from_dict(item) for item in data.get("checkpoints", [])]
    data["events"] = [event_from_dict(item) for item in data.get("events", [])]
    data["summary_nodes"] = [summary_node_from_dict(item) for item in data.get("summary_nodes", [])]
    data["volume_spaces"] = [volume_space_from_dict(item) for item in data.get("volume_spaces", [])]
    data["volume_bridges"] = [volume_bridge_from_dict(item) for item in data.get("volume_bridges", [])]
    data["dirty_ranges"] = [tuple(item) for item in data.get("dirty_ranges", [])]
    data.setdefault("manual_review_queue", [])
    data.setdefault("prompt_output_hashes", [])
    if data.get("style_anchor"):
        data["style_anchor"] = StyleAnchor(**data["style_anchor"])
    if data.get("style_calibration"):
        style_calibration = dict(data["style_calibration"])
        style_calibration["avg_sentence_length"] = tuple(style_calibration["avg_sentence_length"])
        style_calibration["paragraph_length_range"] = tuple(style_calibration["paragraph_length_range"])
        style_calibration["dialogue_ratio_range"] = tuple(style_calibration["dialogue_ratio_range"])
        data["style_calibration"] = StyleCalibrationProfile(**style_calibration)
    return BookProject(**data)
