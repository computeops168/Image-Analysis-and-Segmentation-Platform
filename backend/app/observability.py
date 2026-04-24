from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status_code"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
ACTIVE_REQUESTS = Gauge(
    "http_active_requests",
    "Active in-flight HTTP requests.",
)
LOGIN_ATTEMPTS = Counter(
    "auth_login_attempts_total",
    "Admin login attempts.",
    ["result"],
)
RATE_LIMITED = Counter(
    "rate_limited_total",
    "Rate-limited requests.",
    ["method", "path"],
)
UPLOADS = Counter(
    "uploads_total",
    "Image upload attempts.",
    ["result"],
)
JOBS = Counter(
    "jobs_total",
    "Jobs created and completed by status.",
    ["status"],
)
JOB_DURATION = Histogram(
    "job_duration_seconds",
    "Background job processing duration.",
    ["status"],
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(event_data)
        return json.dumps(payload, separators=(",", ":"))


def setup_logging() -> None:
    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


def _normalize_path(path: str) -> str:
    if path.startswith("/api/jobs/") and path != "/api/jobs":
        return "/api/jobs/{job_id}"
    if path.startswith("/api/files/"):
        return "/api/files/{file_id}"
    return path


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._logger = logging.getLogger("app.http")

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", "").strip() or uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        path_label = _normalize_path(request.url.path)

        ACTIVE_REQUESTS.inc()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(request.method, path_label, "500").inc()
            REQUEST_DURATION.labels(request.method, path_label).observe(duration)
            self._logger.exception(
                "request_failed",
                extra={
                    "event_data": {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "path_label": path_label,
                        "status_code": 500,
                        "duration_ms": int(duration * 1000),
                    }
                },
            )
            raise
        finally:
            ACTIVE_REQUESTS.dec()

        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(request.method, path_label, str(status_code)).inc()
        REQUEST_DURATION.labels(request.method, path_label).observe(duration)
        response.headers["X-Request-ID"] = request_id
        self._logger.info(
            "request_complete",
            extra={
                "event_data": {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "path_label": path_label,
                    "status_code": status_code,
                    "duration_ms": int(duration * 1000),
                    "client_ip": _resolve_client_ip(request),
                }
            },
        )
        return response


def _resolve_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def render_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_login_attempt(success: bool) -> None:
    LOGIN_ATTEMPTS.labels("success" if success else "failure").inc()


def record_rate_limited(method: str, path: str) -> None:
    RATE_LIMITED.labels(method.upper(), _normalize_path(path)).inc()


def record_upload_result(result: str) -> None:
    UPLOADS.labels(result).inc()


def record_job_status(status: str, duration_seconds: float | None = None) -> None:
    JOBS.labels(status).inc()
    if duration_seconds is not None:
        JOB_DURATION.labels(status).observe(max(0.0, duration_seconds))
