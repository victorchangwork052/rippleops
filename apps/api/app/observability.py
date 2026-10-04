"""Structured JSON logging that Cloud Logging parses natively."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}
_REDACT = ("key", "token", "secret", "password", "credential", "authorization")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_var.get(),
        }
        for k, v in record.__dict__.items():
            if k in _RESERVED or k.startswith("_"):
                continue
            payload[k] = "[redacted]" if any(s in k.lower() for s in _REDACT) else v
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["stack"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("httpx", "google", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = rid
            logging.getLogger("rippleops.http").info(
                "request", extra={"method": request.method, "path": request.url.path,
                                  "status": response.status_code,
                                  "duration_ms": int((time.perf_counter() - started) * 1000)})
            return response
        finally:
            request_id_var.reset(token)


class Timer:
    """`with Timer("tool", name="trace_bom_impact"):` logs the execution time."""

    def __init__(self, kind: str, **fields) -> None:
        self.kind, self.fields = kind, fields

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        ms = int((time.perf_counter() - self.started) * 1000)
        logging.getLogger("rippleops.timing").info(
            self.kind, extra={**self.fields, "duration_ms": ms, "ok": exc is None,
                              "error_category": type(exc).__name__ if exc else None})
        return False
