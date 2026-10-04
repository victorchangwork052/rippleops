"""Minimal in-process state for events, analyses, scenarios and actions.

The seeded business data lives in the repository (BigQuery or local seed).
User-created demo state lives here and is cleared by "Reset Demo". Deploy the
API with a single instance so every request sees the same state.
"""

from __future__ import annotations

import itertools
import threading
from datetime import UTC, datetime

from app.db.schema import ChangeEvent
from app.models.actions import Action, ActionPlan, ActionUpdate
from app.models.events import COMPONENT_EVENTS, ChangeEventOut, EventCreate
from app.models.impact import ImpactAnalysis
from app.models.planning import DemandForecast, MaterialPlan, ProductionPlan
from app.models.scenario import ScenarioResult
from app.models.sourcing import SourcingResult, SupplierAssessment
from app.models.workflow import WorkflowRun
from app.services.index import DataIndex


class NotFoundError(KeyError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


EVENT_TITLES = {
    "COMPONENT_EOL": "{part} End-of-Life",
    "SUPPLIER_PRICE_INCREASE": "{part} price increase",
    "MATERIAL_PRICE_CHANGE": "Raw-material price change",
    "FREIGHT_CHANGE": "Freight rate change",
    "OTHER": "{part} change",
}


class DemoStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.reset(None)

    def reset(self, index: DataIndex | None) -> None:
        with self._lock:
            self.events: dict[str, ChangeEventOut] = {}
            self.analyses: dict[str, ImpactAnalysis] = {}  # by event id (latest)
            self.scenarios: dict[str, ScenarioResult] = {}
            self.action_plans: dict[str, ActionPlan] = {}  # by event id (latest)
            self._event_seq = itertools.count(2001)
            # Sourcing and planning results, by event id (latest).
            self.sourcing: dict[str, SourcingResult] = {}
            self.assessments: dict[str, SupplierAssessment] = {}
            self.forecasts: dict[str, DemandForecast] = {}
            self.material_plans: dict[str, MaterialPlan] = {}
            self.production_plans: dict[str, ProductionPlan] = {}  # by plan id
            self.workflow_runs: dict[str, WorkflowRun] = {}  # by event id (latest)
            self._plan_seq = itertools.count(1)
            self._run_seq = itertools.count(1)
            if index is not None:
                for ev in index.snapshot.change_events:
                    self.events[ev.event_id] = self._from_seed(index, ev)

    # -- events -----------------------------------------------------------

    def _from_seed(self, index: DataIndex, ev: ChangeEvent) -> ChangeEventOut:
        sup = index.suppliers.get(ev.supplier_id or "")
        return ChangeEventOut(
            event_id=ev.event_id, event_type=ev.event_type, title=ev.title, summary=ev.summary,
            supplier_id=ev.supplier_id, supplier_name=sup.supplier_name if sup else None,
            affected_item_id=ev.affected_item_id,
            affected_item_name=index.item_name(ev.affected_item_id) if ev.affected_item_id else None,
            event_date=ev.event_date, last_time_buy_date=ev.last_time_buy_date, last_ship_date=ev.last_ship_date,
            recommended_alternative_item_id=ev.recommended_alternative_item_id, source="seed",
            source_document_name=None, extraction_method=None, status=ev.status, created_at=_now(),
            analyzable=ev.event_type in COMPONENT_EVENTS and ev.affected_item_id is not None,
        )

    def create_event(self, index: DataIndex, data: EventCreate) -> ChangeEventOut:
        sp = index.supplier_part.get(data.part_id)
        supplier = index.suppliers.get(sp.supplier_id) if sp else None
        part_name = index.item_name(data.part_id)
        with self._lock:
            event_id = f"EVT-{next(self._event_seq)}"
            summary = f"{supplier.supplier_name if supplier else data.supplier_name or 'Supplier'} notice for " \
                      f"{data.part_id} ({part_name})."
            if data.recommended_alternative_part_id:
                summary += f" Recommended replacement: {data.recommended_alternative_part_id}."
            ev = ChangeEventOut(
                event_id=event_id, event_type=data.event_type,
                title=EVENT_TITLES[data.event_type].format(part=data.part_id), summary=summary,
                supplier_id=supplier.supplier_id if supplier else None,
                supplier_name=supplier.supplier_name if supplier else data.supplier_name,
                affected_item_id=data.part_id, affected_item_name=part_name, event_date=index.as_of,
                last_time_buy_date=data.last_time_buy_date, last_ship_date=data.last_ship_date,
                recommended_alternative_item_id=data.recommended_alternative_part_id, source=data.source,
                source_document_name=data.source_document_name, extraction_method=data.extraction_method,
                status="NEW", created_at=_now(), analyzable=data.event_type in COMPONENT_EVENTS,
            )
            self.events[event_id] = ev
            return ev

    def get_event(self, event_id: str) -> ChangeEventOut:
        with self._lock:
            if event_id not in self.events:
                raise NotFoundError(event_id)
            return self.events[event_id]

    def list_events(self) -> list[ChangeEventOut]:
        with self._lock:
            # Newest user events first, then seeded monitoring events.
            user = sorted((e for e in self.events.values() if e.source != "seed"),
                          key=lambda e: int(e.event_id.split("-")[1]), reverse=True)
            seeded = sorted((e for e in self.events.values() if e.source == "seed"),
                            key=lambda e: e.event_date, reverse=True)
            return user + seeded

    # -- analyses & scenarios --------------------------------------------

    def save_analysis(self, analysis: ImpactAnalysis) -> None:
        with self._lock:
            if analysis.event_id:
                self.analyses[analysis.event_id] = analysis
                ev = self.events.get(analysis.event_id)
                if ev:
                    self.events[ev.event_id] = ev.model_copy(
                        update={"status": "ANALYZED", "latest_analysis_id": analysis.analysis_id})

    def get_analysis(self, event_id: str) -> ImpactAnalysis:
        with self._lock:
            if event_id not in self.analyses:
                raise NotFoundError(event_id)
            return self.analyses[event_id]

    def save_scenario(self, result: ScenarioResult) -> None:
        with self._lock:
            self.scenarios[result.scenario_id] = result
            ev = self.events.get(result.event_id or "")
            if ev:
                self.events[ev.event_id] = ev.model_copy(update={"latest_scenario_id": result.scenario_id})

    def get_scenario(self, scenario_id: str) -> ScenarioResult:
        with self._lock:
            if scenario_id not in self.scenarios:
                raise NotFoundError(scenario_id)
            return self.scenarios[scenario_id]

    def list_scenarios(self, event_id: str | None) -> list[ScenarioResult]:
        with self._lock:
            items = [s for s in self.scenarios.values() if event_id is None or s.event_id == event_id]
            return sorted(items, key=lambda s: s.created_at, reverse=True)


    # -- action plans ------------------------------------------------------

    def save_plan(self, plan: ActionPlan) -> None:
        with self._lock:
            self.action_plans[plan.event_id] = plan

    def get_plan(self, event_id: str) -> ActionPlan:
        with self._lock:
            if event_id not in self.action_plans:
                raise NotFoundError(event_id)
            return self.action_plans[event_id]

    def update_action(self, action_id: str, update: ActionUpdate) -> Action:
        with self._lock:
            for event_id, plan in self.action_plans.items():
                for i, action in enumerate(plan.actions):
                    if action.action_id == action_id:
                        changed = action.model_copy(update=update.model_dump(exclude_none=True))
                        actions = list(plan.actions)
                        actions[i] = changed
                        self.action_plans[event_id] = plan.model_copy(update={"actions": actions})
                        return changed
            raise NotFoundError(action_id)

    # -- production plans and agent runs --------------------------------------

    def next_plan_id(self, event_id: str | None) -> str:
        with self._lock:
            return f"PLAN-{event_id or 'ADHOC'}-{next(self._plan_seq):02d}"

    def next_run_id(self) -> str:
        with self._lock:
            return f"RUN-{next(self._run_seq):04d}"

    def save_production_plan(self, plan: ProductionPlan) -> None:
        with self._lock:
            self.production_plans[plan.plan_id] = plan

    def get_production_plan(self, plan_id: str) -> ProductionPlan:
        with self._lock:
            if plan_id not in self.production_plans:
                raise NotFoundError(plan_id)
            return self.production_plans[plan_id]

    def event_plans(self, event_id: str) -> list[ProductionPlan]:
        with self._lock:
            return [p for p in self.production_plans.values() if p.event_id == event_id]

    def set_plan_status(self, plan_id: str, **update) -> ProductionPlan:
        with self._lock:
            plan = self.get_production_plan(plan_id).model_copy(update=update)
            self.production_plans[plan_id] = plan
            return plan

    def all_actions(self) -> list[Action]:
        with self._lock:
            return [a for plan in self.action_plans.values() for a in plan.actions]


_store = DemoStore()


def get_store() -> DemoStore:
    return _store
