"""Events, impact analysis and scenarios."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import UserFacingError, repo, settings, store
from app.config import Settings
from app.db.repository import Repository
from app.models.events import ChangeEventOut, EventCreate
from app.models.impact import ImpactAnalysis
from app.models.notice import ParsedNotice, ParseRequest
from app.models.scenario import ScenarioRequest, ScenarioResult
from app.observability import Timer
from app.services.impact import analyze_impact, validate_component
from app.services.notice import NoticeReadError, extract_text, parse_notice, sanitize_filename
from app.services.scenario import run_scenario
from app.services.store import DemoStore

router = APIRouter(prefix="/api")


# -- events -----------------------------------------------------------------


@router.get("/events", response_model=list[ChangeEventOut])
def list_events(st: DemoStore = Depends(store)):
    return st.list_events()


class SupplierOption(BaseModel):
    supplier_id: str
    supplier_name: str
    country: str


class PartOption(BaseModel):
    part_id: str
    part_name: str
    supplier_name: str | None
    status: str


class AlternateOption(BaseModel):
    source_part_id: str
    alternative_part_id: str
    approval_status: str


class EventFormOptions(BaseModel):
    suppliers: list[SupplierOption]
    parts: list[PartOption]
    alternates: list[AlternateOption]


@router.get("/events/options", response_model=EventFormOptions)
def event_form_options(rp: Repository = Depends(repo)):
    """Choices for the supplier / part / replacement pickers on the event form."""
    index = rp.index()
    parts = []
    for item in sorted(index.items.values(), key=lambda i: i.item_id):
        if item.item_type != "COMPONENT":
            continue
        sp = index.supplier_part.get(item.item_id)
        supplier = index.suppliers.get(sp.supplier_id) if sp else None
        parts.append(PartOption(part_id=item.item_id, part_name=item.item_name,
                                supplier_name=supplier.supplier_name if supplier else None, status=item.status))
    # Part-level alternates only; product-specific approvals are resolved during analysis.
    alternates = {(a.source_part_id, a.alternative_part_id): a
                  for a in index.snapshot.alternate_parts if a.product_id is None}
    return EventFormOptions(
        suppliers=[SupplierOption(supplier_id=s.supplier_id, supplier_name=s.supplier_name, country=s.country)
                   for s in sorted(index.suppliers.values(), key=lambda s: s.supplier_name)],
        parts=parts,
        alternates=[AlternateOption(source_part_id=a.source_part_id, alternative_part_id=a.alternative_part_id,
                                    approval_status=a.approval_status) for a in alternates.values()])


@router.post("/events", response_model=ChangeEventOut, status_code=201)
def create_event(body: EventCreate, st: DemoStore = Depends(store), rp: Repository = Depends(repo)):
    index = rp.index()
    part_id = body.part_id.strip().upper()
    alt = body.recommended_alternative_part_id.strip().upper() if body.recommended_alternative_part_id else None
    try:
        validate_component(index, part_id)
    except ValueError as exc:
        raise UserFacingError(
            f"We couldn't find part '{part_id}' in the product data. "
            "Review the extracted information or enter the part manually.", code="unknown_part") from exc
    if alt and alt not in index.items:
        raise UserFacingError(f"Recommended replacement '{alt}' is not in the product data.", code="unknown_part")
    return st.create_event(index, body.model_copy(update={"part_id": part_id, "recommended_alternative_part_id": alt}))


@router.post("/events/parse", response_model=ParsedNotice)
def parse_event_text(body: ParseRequest, rp: Repository = Depends(repo)):
    """Extract a structured change event from notice text (Gemini, rule-based fallback)."""
    name = sanitize_filename(body.document_name) if body.document_name else None
    with Timer("tool", tool="parse_change_notice"):
        return parse_notice(rp.index(), body.document_text, name, "demo" if name else "manual")


@router.post("/events/parse-upload", response_model=ParsedNotice)
async def parse_event_upload(file: UploadFile = File(...), rp: Repository = Depends(repo),
                             cfg: Settings = Depends(settings)):
    name = sanitize_filename(file.filename)
    data = await file.read(cfg.max_upload_bytes + 1)
    if len(data) > cfg.max_upload_bytes:
        raise UserFacingError("This file is larger than 2 MB. Please upload a smaller notice.", code="file_too_large")
    try:
        text = extract_text(name, data)
    except NoticeReadError as exc:
        raise UserFacingError(str(exc), code="unreadable_document") from exc
    with Timer("tool", tool="parse_change_notice"):
        return parse_notice(rp.index(), text, name, "upload")


@router.get("/events/{event_id}", response_model=ChangeEventOut)
def get_event(event_id: str, st: DemoStore = Depends(store)):
    return st.get_event(event_id)


# -- impact -----------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    event_id: str
    margin_threshold: float | None = Field(default=None, ge=0.0, lt=1.0)


def analyze_event(st: DemoStore, rp: Repository, cfg: Settings, event_id: str,
                  margin_threshold: float | None = None) -> ImpactAnalysis:
    ev = st.get_event(event_id)
    if not ev.analyzable or not ev.affected_item_id:
        raise UserFacingError("This event is not linked to a single component, so it cannot be traced through "
                              "the BOM. Use the Scenario Simulator to model it.", code="not_analyzable")
    with Timer("tool", tool="calculate_business_impact", part_id=ev.affected_item_id):
        analysis = analyze_impact(rp, ev.affected_item_id, margin_threshold or cfg.default_margin_threshold,
                                  cfg.demand_horizon_months, event_id=ev.event_id,
                                  preferred_alternative=ev.recommended_alternative_item_id)
    st.save_analysis(analysis)
    return analysis


@router.post("/impact/analyze", response_model=ImpactAnalysis)
def analyze(body: AnalyzeRequest, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
            cfg: Settings = Depends(settings)):
    return analyze_event(st, rp, cfg, body.event_id, body.margin_threshold)


@router.get("/impact/{event_id}", response_model=ImpactAnalysis)
def get_impact(event_id: str, st: DemoStore = Depends(store)):
    return st.get_analysis(event_id)


# -- scenarios --------------------------------------------------------------


def run_event_scenario(st: DemoStore, rp: Repository, cfg: Settings, body: ScenarioRequest) -> ScenarioResult:
    part_id = body.part_id
    if body.event_id:
        ev = st.get_event(body.event_id)
        part_id = part_id or ev.affected_item_id
    if not part_id:
        raise UserFacingError("Choose an event or a component to run a scenario.", code="missing_part")
    with Timer("tool", tool="run_scenario", part_id=part_id):
        result = run_scenario(rp, part_id, body, cfg.demand_horizon_months)
    st.save_scenario(result)
    return result


@router.post("/scenarios/run", response_model=ScenarioResult)
def scenarios_run(body: ScenarioRequest, st: DemoStore = Depends(store), rp: Repository = Depends(repo),
                  cfg: Settings = Depends(settings)):
    return run_event_scenario(st, rp, cfg, body)


@router.get("/scenarios", response_model=list[ScenarioResult])
def scenarios_list(event_id: str | None = None, st: DemoStore = Depends(store)):
    return st.list_scenarios(event_id)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResult)
def scenarios_get(scenario_id: str, st: DemoStore = Depends(store)):
    return st.get_scenario(scenario_id)
