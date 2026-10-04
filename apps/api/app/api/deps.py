from __future__ import annotations

from app.config import Settings, get_settings
from app.db.repository import Repository, get_repository
from app.services.store import DemoStore, get_store


class UserFacingError(Exception):
    """An error whose message is safe and useful to show in the UI."""

    def __init__(self, message: str, status_code: int = 422, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def repo() -> Repository:
    return get_repository()


def store() -> DemoStore:
    s = get_store()
    if not s.events:  # first request after start-up: load seeded monitoring events
        s.reset(get_repository().index())
    return s


def settings() -> Settings:
    return get_settings()
