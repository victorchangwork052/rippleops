"""BigQuery-backed repository (DATA_BACKEND=bigquery)."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db.schema import TABLES, Snapshot
from app.models.bom import BomPath, BomTrace
from app.services.bom import order_edge_chain, summarize_paths, trace_in_memory
from app.services.index import DataIndex

log = logging.getLogger("rippleops.bigquery")
SQL_DIR = Path(__file__).parent / "sql"


def load_sql(name: str, dataset: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8").replace("{dataset}", dataset)


def _coerce(value: Any, annotation: str) -> Any:
    if value is None:
        return None
    if "float" in annotation:
        return float(value) if isinstance(value, (Decimal, int, float)) else float(value)
    if "int" in annotation:
        return int(value)
    if "date" in annotation and not isinstance(value, date):
        return date.fromisoformat(str(value))
    return value


def parse_edge_strings(product_id: str, component_id: str, raw: list[str]) -> BomPath:
    edges = []
    for item in raw:
        parent, child, qty = item.split("|")
        edges.append((parent, child, float(qty)))
    return order_edge_chain(product_id, component_id, edges)


class BigQueryRepository:
    backend = "bigquery"

    def __init__(self, settings: Settings) -> None:
        from google.cloud import bigquery

        self._bq = bigquery
        self._settings = settings
        self._client = bigquery.Client(project=settings.google_cloud_project or None)
        self._dataset = f"{self._client.project}.{settings.bigquery_dataset}"
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._index: DataIndex | None = None
        # Set when BigQuery Graph is unavailable for this project (e.g. no Enterprise
        # reservation), so later requests go straight to recursive SQL.
        self._graph_unavailable = False
        self._forecasts: dict[tuple, dict[str, list[tuple[float, float, float]]]] = {}

    # -- tables -------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        with self._lock:
            if self._snapshot is None:
                self._snapshot = self._load()
            return self._snapshot

    def index(self) -> DataIndex:
        snap = self.snapshot()
        with self._lock:
            if self._index is None:
                self._index = DataIndex.build(snap, self._settings.demo_as_of)
            return self._index

    def reload(self) -> None:
        with self._lock:
            self._snapshot = None
            self._index = None
            self._forecasts.clear()

    def _load_table(self, table: str, row_type: type) -> list:
        annotations = {f.name: str(f.type) for f in fields(row_type)}
        rows = self._client.query(f"SELECT * FROM `{self._dataset}.{table}`").result()
        return [row_type(**{name: _coerce(row.get(name), ann) for name, ann in annotations.items()}) for row in rows]

    def _load(self) -> Snapshot:
        started = time.perf_counter()
        snap = Snapshot()
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = {table: pool.submit(self._load_table, table, row_type) for table, row_type in TABLES.items()}
            for table, job in jobs.items():
                setattr(snap, table, job.result())
        log.info("bigquery.snapshot_loaded", extra={"duration_ms": int((time.perf_counter() - started) * 1000)})
        return snap

    # -- graph traversal ----------------------------------------------------

    def trace(self, component_id: str) -> BomTrace:
        params = [
            self._bq.ScalarQueryParameter("part_id", "STRING", component_id),
            self._bq.ScalarQueryParameter("as_of", "DATE", self._settings.demo_as_of),
        ]
        strategies = [("bigquery_graph", "trace_bom_impact.gql"), ("recursive_sql", "trace_bom_impact_recursive.sql")]
        if self._graph_unavailable:
            strategies = strategies[1:]
        for method, sql_file in strategies:
            started = time.perf_counter()
            try:
                job = self._client.query(load_sql(sql_file, self._dataset),
                                         job_config=self._bq.QueryJobConfig(query_parameters=params))
                paths = [parse_edge_strings(r["product_id"], component_id, list(r["edges"])) for r in job.result()]
                log.info("bigquery.trace_ok", extra={
                    "method": method, "paths": len(paths),
                    "duration_ms": int((time.perf_counter() - started) * 1000)})
                return summarize_paths(component_id, paths, method)
            except Exception as exc:  # noqa: BLE001 - fall through to the next strategy
                if method == "bigquery_graph" and "reservation" in str(exc).lower():
                    self._graph_unavailable = True
                log.warning("bigquery.trace_failed", extra={"method": method, "error": type(exc).__name__,
                                                           "detail": str(exc)[:300]})
        # Last resort: traverse the BigQuery-loaded edges in memory.
        return trace_in_memory(self.index(), component_id)

    # -- forecasting -------------------------------------------------------------

    def ai_forecast(self, product_ids: list[str], horizon: int, confidence: float
                    ) -> dict[str, list[tuple[float, float, float]]]:
        """(forecast, lower, upper) per product and month from BigQuery AI.FORECAST (TimesFM)."""
        key = (tuple(sorted(product_ids)), horizon, confidence)
        if key in self._forecasts:
            return self._forecasts[key]
        sql = load_sql("forecast_demand.sql", self._dataset).replace("{horizon}", str(int(horizon))).replace(
            "{confidence}", f"{float(confidence):.2f}")
        params = [self._bq.ArrayQueryParameter("product_ids", "STRING", sorted(product_ids))]
        started = time.perf_counter()
        rows = self._client.query(sql, job_config=self._bq.QueryJobConfig(query_parameters=params)).result()
        out: dict[str, list[tuple[float, float, float]]] = {}
        for r in rows:
            out.setdefault(r["product_id"], []).append((
                float(round(r["forecast_value"])), float(round(r["prediction_interval_lower_bound"])),
                float(round(r["prediction_interval_upper_bound"]))))
        log.info("bigquery.forecast_ok", extra={"products": len(out),
                                                "duration_ms": int((time.perf_counter() - started) * 1000)})
        self._forecasts[key] = out
        return out
