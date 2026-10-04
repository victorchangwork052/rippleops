"""Thin wrapper around the Google GenAI SDK (Vertex AI or Gemini API key)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import get_settings
from app.observability import Timer

log = logging.getLogger("rippleops.gemini")
T = TypeVar("T", bound=BaseModel)
TIMEOUT_MS = 30_000


class GeminiUnavailable(RuntimeError):
    """Gemini is not configured or the call failed; callers fall back deterministically."""


@lru_cache
def get_client():
    settings = get_settings()
    if not settings.gemini_configured:
        raise GeminiUnavailable("Gemini is not configured")
    from google import genai
    from google.genai import types

    http = types.HttpOptions(timeout=TIMEOUT_MS)
    if settings.gemini_api_key:
        return genai.Client(api_key=settings.gemini_api_key, http_options=http)
    return genai.Client(vertexai=True, project=settings.google_cloud_project,
                        location=settings.google_cloud_location, http_options=http)


def generate_structured(system: str, contents: list[Any], schema: type[T], *, purpose: str,
                        prompt_version: str) -> T:
    """Call Gemini with a response schema and return the validated model."""
    from google.genai import types

    settings = get_settings()
    with Timer("gemini_call", purpose=purpose, prompt_version=prompt_version, model=settings.gemini_model):
        try:
            response = get_client().models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system, temperature=0.0, response_mime_type="application/json",
                    response_schema=schema),
            )
        except GeminiUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - any SDK / network failure means "fall back"
            log.warning("gemini_failed", extra={"purpose": purpose, "error_category": type(exc).__name__,
                                                "detail": str(exc)[:300]})
            raise GeminiUnavailable(type(exc).__name__) from exc
    parsed = response.parsed
    if isinstance(parsed, schema):
        return parsed
    try:
        return schema.model_validate_json(response.text or "")
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini_invalid_json", extra={"purpose": purpose})
        raise GeminiUnavailable("Invalid structured response") from exc


def generate_text(system: str, contents: list[Any], *, purpose: str, prompt_version: str) -> str:
    from google.genai import types

    settings = get_settings()
    with Timer("gemini_call", purpose=purpose, prompt_version=prompt_version, model=settings.gemini_model):
        try:
            response = get_client().models.generate_content(
                model=settings.gemini_model, contents=contents,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.2))
        except GeminiUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("gemini_failed", extra={"purpose": purpose, "error_category": type(exc).__name__,
                                                "detail": str(exc)[:300]})
            raise GeminiUnavailable(type(exc).__name__) from exc
    text = (response.text or "").strip()
    if not text:
        raise GeminiUnavailable("Empty response")
    return text
