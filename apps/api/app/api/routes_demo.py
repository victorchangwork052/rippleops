"""Demo control, reference data and the Data browser."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import UserFacingError, repo, settings, store
from app.api.routes_core import analyze_event
from app.config import Settings
from app.db.repository import Repository
from app.db.schema import TABLES
from app.models.events import ChangeEventOut, EventCreate
from app.services.store import DemoStore

router = APIRouter(prefix="/api")

DOCUMENTS = Path(__file__).resolve().parent.parent / "seed" / "documents"
SAMPLE_NOTICE = "novachip_mcu_x100_eol_notice.txt"

# The canonical fields of the sample notice, used by "Load Demo Scenario" and as
# the "Use Extracted Demo Data" fallback when document parsing fails.
DEMO_EVENT = EventCreate(
    event_type="COMPONENT_EOL", supplier_name="NovaChip Technologies", part_id="MCU-X100",
    last_time_buy_date=date(2027, 1, 30), last_ship_date=date(2027, 3, 31),
    recommended_alternative_part_id="MCU-X200", source="demo", source_document_name=SAMPLE_NOTICE,
    extraction_method="demo_data",
)


class SampleNotice(BaseModel):
    filename: str
    text: str


class DemoLoadResult(BaseModel):
    event: ChangeEventOut
    analysis_id: str


class HealthOut(BaseModel):
    status: str
    app_env: str
    data_backend: str
    gemini_configured: bool
    gemini_model: str


@router.get("/health", response_model=HealthOut)
def health(cfg: Settings = Depends(settings), rp: Repository = Depends(repo)):
    return HealthOut(status="ok", app_env=cfg.app_env, data_backend=rp.backend,
                     gemini_configured=cfg.gemini_configured, gemini_model=cfg.gemini_model)


@router.get("/demo/sample-notice", response_model=SampleNotice)
def sample_notice():
    return SampleNotice(filename=SAMPLE_NOTICE, text=(DOCUMENTS / SAMPLE_NOTICE).read_text(encoding="utf-8"))


@router.post("/demo/reset")
def demo_reset(st: DemoStore = Depends(store), rp: Repository = Depends(repo)):
    rp.reload()
    st.reset(rp.index())
    return {"status": "reset", "events": len(st.events)}


@router.post("/demo/load", response_model=DemoLoadResult)
def demo_load(st: DemoStore = Depends(store), rp: Repository = Depends(repo), cfg: Settings = Depends(settings)):
    """Create the NovaChip MCU-X100 EOL event and analyze it in one step."""
    event = st.create_event(rp.index(), DEMO_EVENT)
    analysis = analyze_event(st, rp, cfg, event.event_id)
    return DemoLoadResult(event=st.get_event(event.event_id), analysis_id=analysis.analysis_id)


@router.get("/demo/event-template", response_model=EventCreate)
def demo_event_template():
    return DEMO_EVENT


# -- reference data for scenario controls ---------------------------------


class MaterialOut(BaseModel):
    material_code: str
    price_per_kg: float
    currency: str


class LaneOut(BaseModel):
    shipping_lane_id: str
    origin: str
    destination: str
    mode: str
    freight_rate_per_kg: float


class ReferenceOut(BaseModel):
    materials: list[MaterialOut]
    shipping_lanes: list[LaneOut]
    as_of_date: str
    default_margin_threshold: float
    horizon_months: int


@router.get("/reference", response_model=ReferenceOut)
def reference(rp: Repository = Depends(repo), cfg: Settings = Depends(settings)):
    idx = rp.index()
    return ReferenceOut(
        materials=[MaterialOut(material_code=k, price_per_kg=v, currency="USD")
                   for k, v in sorted(idx.material_price.items())],
        shipping_lanes=[LaneOut(**{k: getattr(lane, k) for k in LaneOut.model_fields})
                        for lane in idx.snapshot.shipping_lanes],
        as_of_date=idx.as_of.isoformat(), default_margin_threshold=cfg.default_margin_threshold,
        horizon_months=cfg.demand_horizon_months)


# -- data browser -----------------------------------------------------------


class TableSummary(BaseModel):
    name: str
    rows: int
    columns: list[str]


class DataSummary(BaseModel):
    data_source: str
    as_of_date: str
    tables: list[TableSummary]


class TablePage(BaseModel):
    name: str
    columns: list[str]
    total: int
    rows: list[dict]


@router.get("/data/summary", response_model=DataSummary)
def data_summary(rp: Repository = Depends(repo)):
    snap = rp.snapshot()
    return DataSummary(
        data_source=rp.backend, as_of_date=rp.index().as_of.isoformat(),
        tables=[TableSummary(name=n, rows=len(snap.table(n)), columns=list(t.__dataclass_fields__))
                for n, t in TABLES.items()])


@router.get("/data/tables/{name}", response_model=TablePage)
def data_table(name: str, q: str | None = Query(default=None, max_length=64), limit: int = Query(50, ge=1, le=500),
               offset: int = Query(0, ge=0), rp: Repository = Depends(repo)):
    if name not in TABLES:
        raise UserFacingError(f"Unknown table '{name}'.", status_code=404, code="not_found")
    rows = [asdict(r) for r in rp.snapshot().table(name)]
    if q:
        needle = q.lower()
        rows = [r for r in rows if any(needle in str(v).lower() for v in r.values())]
    return TablePage(name=name, columns=list(TABLES[name].__dataclass_fields__), total=len(rows),
                     rows=rows[offset:offset + limit])
