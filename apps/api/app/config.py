"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file() -> None:
    """Minimal .env support for local development; real environment variables win."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    app_env: str
    data_backend: str  # "local" | "bigquery"
    google_cloud_project: str
    google_cloud_location: str
    bigquery_dataset: str
    gemini_model: str
    gemini_api_key: str
    use_vertex_ai: bool
    cors_origins: tuple[str, ...]
    # Fixed "today" for the demo so results never drift with the calendar.
    demo_as_of: date
    demand_horizon_months: int
    default_margin_threshold: float
    max_upload_bytes: int

    @property
    def gemini_configured(self) -> bool:
        if self.gemini_api_key:
            return True
        return self.use_vertex_ai and bool(self.google_cloud_project)


@lru_cache
def get_settings() -> Settings:
    _load_env_file()
    return Settings(
        app_env=_env("APP_ENV", "development"),
        data_backend=_env("DATA_BACKEND", "local").lower(),
        google_cloud_project=_env("GOOGLE_CLOUD_PROJECT"),
        google_cloud_location=_env("GOOGLE_CLOUD_LOCATION", "us-central1"),
        bigquery_dataset=_env("BIGQUERY_DATASET", "rippleops"),
        gemini_model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
        gemini_api_key=_env("GEMINI_API_KEY"),
        use_vertex_ai=_env("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in ("1", "true", "yes"),
        cors_origins=tuple(
            o.strip() for o in _env("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        ),
        demo_as_of=date.fromisoformat(_env("DEMO_AS_OF", "2026-10-01")),
        demand_horizon_months=int(_env("DEMAND_HORIZON_MONTHS", "6")),
        default_margin_threshold=float(_env("DEFAULT_MARGIN_THRESHOLD", "0.20")),
        max_upload_bytes=int(_env("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))),
    )
