from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import BookProject, Checkpoint, utc_now
from .serialization import project_from_dict, to_plain


class JsonStore:
    def __init__(self, root: Path | str = "data") -> None:
        self.root = Path(root)
        self.projects_dir = self.root / "projects"
        self.checkpoints_dir = self.root / "checkpoints"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[BookProject]:
        projects = []
        for path in sorted(self.projects_dir.glob("*.json")):
            projects.append(self.load_project(path.stem))
        return projects

    def load_project(self, project_id: str) -> BookProject:
        path = self.projects_dir / f"{project_id}.json"
        if not path.exists():
            raise KeyError(f"project not found: {project_id}")
        return project_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_project(self, project: BookProject) -> None:
        project.updated_at = utc_now()
        path = self.projects_dir / f"{project.id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(to_plain(project), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def delete_project(self, project_id: str) -> None:
        path = self.projects_dir / f"{project_id}.json"
        if not path.exists():
            return
        try:
            project = self.load_project(project_id)
            for checkpoint in project.checkpoints:
                cp_path = Path(checkpoint.payload_path)
                if cp_path.exists():
                    cp_path.unlink(missing_ok=True)
        except Exception:
            pass
        path.unlink(missing_ok=True)

    def save_checkpoint_payload(self, checkpoint_id: str, payload: dict[str, Any]) -> tuple[str, str]:
        plain = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        content_hash = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        path = self.checkpoints_dir / f"{checkpoint_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(plain, encoding="utf-8")
        tmp.replace(path)
        return str(path), content_hash

    def load_checkpoint_payload(self, checkpoint: Checkpoint) -> dict[str, Any]:
        path = Path(checkpoint.payload_path)
        if not path.exists():
            raise KeyError(f"checkpoint payload not found: {checkpoint.id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = checkpoint.content_hash
        actual = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if expected != actual:
            raise ValueError(f"checkpoint hash mismatch: {checkpoint.id}")
        return self.migrate_checkpoint_payload(payload)

    @staticmethod
    def migrate_checkpoint_payload(payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload.setdefault("schema_version", 1)
        payload.setdefault("context_layers", {
            "style_anchor": {},
            "structural_summary": {},
            "narrative_state": {},
            "immediate_context": {},
        })
        project = payload.get("project")
        if isinstance(project, dict):
            project.setdefault("manual_review_queue", [])
            project.setdefault("dirty_ranges", [])
            project.setdefault("prompt_output_hashes", [])
            for checkpoint in project.get("checkpoints", []):
                checkpoint.setdefault("schema_version", 1)
                checkpoint.setdefault("style_anchor_hash", None)
        return payload
