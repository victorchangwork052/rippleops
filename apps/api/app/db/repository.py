"""Data access: one interface, two backends.

* `LocalRepository` serves the seeded dataset from memory. It is used for
  tests and for running the demo without Google Cloud credentials.
* `BigQueryRepository` reads the same tables from BigQuery and traces the BOM
  with BigQuery Graph (GQL), falling back to recursive SQL.

Both return identical structured results for the seeded dataset.
"""

from __future__ import annotations

import logging
import threading
from datetime import date
from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.db.schema import Snapshot
from app.models.bom import BomTrace
from app.seed.generator import generate
from app.services.bom import trace_in_memory
from app.services.index import DataIndex

log = logging.getLogger("rippleops.data")


class Repository(Protocol):
    backend: str

    def snapshot(self) -> Snapshot: ...

    def index(self) -> DataIndex: ...

    def trace(self, component_id: str) -> BomTrace: ...

    def reload(self) -> None: ...


class LocalRepository:
    backend = "local_seed"

    def __init__(self, as_of: date) -> None:
        self._as_of = as_of
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._index: DataIndex | None = None

    def snapshot(self) -> Snapshot:
        with self._lock:
            if self._snapshot is None:
                self._snapshot = generate()
            return self._snapshot

    def index(self) -> DataIndex:
        snap = self.snapshot()
        with self._lock:
            if self._index is None:
                self._index = DataIndex.build(snap, self._as_of)
            return self._index

    def trace(self, component_id: str) -> BomTrace:
        return trace_in_memory(self.index(), component_id)

    def reload(self) -> None:
        with self._lock:
            self._snapshot = None
            self._index = None


@lru_cache
def get_repository() -> Repository:
    settings = get_settings()
    if settings.data_backend == "bigquery":
        from app.db.bigquery_repo import BigQueryRepository

        return BigQueryRepository(settings)
    return LocalRepository(settings.demo_as_of)
