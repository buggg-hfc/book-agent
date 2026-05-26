from __future__ import annotations

import json
import mimetypes
import time as _time
from uuid import uuid4
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .serialization import to_plain
from .services import BookAgentService


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
SERVICE = BookAgentService(ROOT / "data")


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "BookAgentMVP/0.1"

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers()
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _handle(self, method: str) -> None:
        request_id = f"req_{uuid4().hex[:12]}"
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            SERVICE.logger.info("request request_id=%s method=%s path=%s", request_id, method, path)
            if path.startswith("/api"):
                # SSE route: bypass JSON routing and response wrapping
                parts = [p for p in path.split("/") if p]
                if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "stream":
                    self._handle_sse(parts[2])
                    return
                result = self._route_api(method, path, parse_qs(parsed.query))
                self._send_json(result)
                return
            self._serve_static(path)
        except ApiError as exc:
            SERVICE.logger.info("request_failed request_id=%s status=%s error=%s", request_id, exc.status, exc.message)
            self._send_json({"error": exc.message}, status=exc.status)
        except KeyError as exc:
            SERVICE.logger.info("request_failed request_id=%s status=%s error=%s", request_id, HTTPStatus.NOT_FOUND, exc)
            self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            SERVICE.logger.exception("request_failed request_id=%s status=%s", request_id, HTTPStatus.INTERNAL_SERVER_ERROR)
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_sse(self, job_id: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        idle_timeout = SERVICE.config.job_timeout_seconds + 30
        last_activity = _time.monotonic()
        while _time.monotonic() - last_activity < idle_timeout:
            events = SERVICE.jobs.drain_events(job_id)
            for evt in events:
                last_activity = _time.monotonic()
                data = json.dumps(to_plain(evt), ensure_ascii=False)
                try:
                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                if evt.event_type in {"completed", "failed"}:
                    return
            try:
                self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            _time.sleep(0.25)

    def _route_api(self, method: str, path: str, query: dict[str, list[str]]) -> object:
        parts = [part for part in path.split("/") if part]
        if method == "GET" and parts == ["api", "health"]:
            return {"ok": True}
        if method == "GET" and parts == ["api", "llm", "config"]:
            return {"config": SERVICE.llm_config()}
        if method == "POST" and parts == ["api", "llm", "reload"]:
            return {"config": SERVICE.reload_llm_config()}
        if method == "GET" and parts == ["api", "settings"]:
            return {"settings": SERVICE.get_settings()}
        if method == "POST" and parts == ["api", "settings"]:
            return {"settings": SERVICE.update_settings(self._read_json())}
        if method == "POST" and parts == ["api", "llm", "generate"]:
            return {"result": SERVICE.call_llm_text(self._read_json())}
        if method == "POST" and parts == ["api", "llm", "structured"]:
            return {"result": SERVICE.call_llm_structured(self._read_json())}
        if method == "GET" and parts == ["api", "projects"]:
            return {"projects": [self._project_summary(project) for project in SERVICE.list_projects()]}
        if method == "POST" and parts == ["api", "projects"]:
            return {"project": to_plain(SERVICE.create_project(self._read_json()))}
        if method == "DELETE" and len(parts) == 3 and parts[:2] == ["api", "projects"]:
            SERVICE.delete_project(parts[2])
            return {"ok": True, "project_id": parts[2]}
        if method == "POST" and parts == ["api", "params", "suggest"]:
            return {"suggestions": SERVICE.suggest_params(self._read_json())}
        if method == "POST" and parts == ["api", "params", "refine"]:
            return {"result": SERVICE.refine_param(self._read_json())}
        if method == "GET" and len(parts) == 3 and parts[:2] == ["api", "projects"]:
            return {"project": to_plain(SERVICE.get_project(parts[2]))}
        if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "tracking":
            project = SERVICE.get_project(parts[2])
            return {"tracking_tables": project.theme_tracking_tables}
        if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "reports":
            project = SERVICE.get_project(parts[2])
            return {"reports": [to_plain(report) for report in project.audit_reports]}
        if method == "POST" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:5] == ["chapters", "generate"]:
            job = SERVICE.start_generate_chapter(parts[2])
            return {"job_id": job.id, "job": to_plain(job)}
        if method == "POST" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:5] == ["chapters", "demo"]:
            count = int(query.get("count", ["3"])[0])
            jobs = SERVICE.start_generate_demo(parts[2], count=count)
            return {"job_ids": [j.id for j in jobs], "jobs": [to_plain(j) for j in jobs]}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "revise":
            return {"project": to_plain(SERVICE.revise_latest_chapter(parts[2]))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "accept_warnings":
            return {"project": to_plain(SERVICE.accept_latest_warnings(parts[2]))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "manual_review":
            return {"project": to_plain(SERVICE.mark_latest_manual_review(parts[2]))}
        if method == "POST" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "chapters":
            body = self._read_json()
            return {"project": to_plain(SERVICE.edit_chapter(parts[2], int(parts[4]), str(body.get("text", ""))))}
        if method == "POST" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "restore":
            return {"project": to_plain(SERVICE.restore_checkpoint(parts[2], parts[4]))}
        if method == "GET" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "restore_diff":
            return {"diff": SERVICE.restore_diff(parts[2], parts[4])}
        if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "restore_validation":
            return {"validation": to_plain(SERVICE.validate_restore(parts[2]))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "manual_checkpoint":
            return {"checkpoint": to_plain(SERVICE.create_manual_checkpoint(parts[2]))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "arc_checkpoint":
            return {"checkpoint": to_plain(SERVICE.create_arc_checkpoint(parts[2]))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "volume_checkpoint":
            return {"checkpoint": to_plain(SERVICE.create_volume_checkpoint(parts[2]))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "emergency_checkpoint":
            return {"checkpoint": to_plain(SERVICE.create_emergency_checkpoint(parts[2]))}
        if method == "POST" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "replay":
            return {"project": to_plain(SERVICE.replay_events_from_checkpoint(parts[2], parts[4]))}
        if method == "GET" and len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "export":
            return {"export": SERVICE.export_project(parts[2], parts[4])}
        if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "scan":
            return {"findings": [to_plain(item) for item in SERVICE.global_scan(parts[2])]}
        if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "align":
            query_text = query.get("q", [""])[0]
            return {"hits": [to_plain(item) for item in SERVICE.align(parts[2], query_text)]}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "volume_bridge":
            confirm = query.get("confirm", ["false"])[0].lower() == "true"
            return {"bridge": to_plain(SERVICE.generate_volume_bridge(parts[2], confirm=confirm))}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "confirm_volume_bridge":
            return {"bridge": to_plain(SERVICE.confirm_volume_bridge(parts[2]))}
        if method == "GET" and parts == ["api", "jobs"]:
            return {"jobs": [to_plain(job) for job in SERVICE.jobs.list()]}
        if method == "POST" and len(parts) == 4 and parts[:2] == ["api", "jobs"]:
            action = parts[3]
            job_id = parts[2]
            if action == "pause":
                return {"job": to_plain(SERVICE.jobs.pause(job_id))}
            if action == "resume":
                return {"job": to_plain(SERVICE.jobs.resume(job_id))}
            if action == "cancel":
                return {"job": to_plain(SERVICE.jobs.cancel(job_id))}
            if action == "retry":
                return {"job": to_plain(SERVICE.jobs.retry(job_id))}
        raise ApiError(HTTPStatus.NOT_FOUND, f"unknown route: {method} {path}")

    def _project_summary(self, project) -> dict[str, object]:
        latest = project.audit_reports[-1] if project.audit_reports else None
        return {
            "id": project.id,
            "title": project.meta.get("title"),
            "theme": project.meta.get("theme"),
            "scale": project.meta.get("scale"),
            "chapter_count": len(project.chapters),
            "checkpoint_count": len(project.checkpoints),
            "latest_status": latest.overall_status if latest else None,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path: str) -> None:
        if path == "/":
            file_path = STATIC_DIR / "index.html"
        else:
            file_path = (STATIC_DIR / path.lstrip("/")).resolve()
            if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
                raise ApiError(HTTPStatus.FORBIDDEN, "forbidden")
        if not file_path.exists() or not file_path.is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "not found")
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Book Agent MVP running at http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    import os

    run(os.getenv("BOOK_AGENT_HOST", "127.0.0.1"), int(os.getenv("BOOK_AGENT_PORT", "8000")))
