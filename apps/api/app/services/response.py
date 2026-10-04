"""One place to compute (and cache) the response artifacts for an event.

The API routes and the ADK agent tools both go through `EventContext`, so a
number shown on a page is the same number an agent saw in its tool output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.db.repository import Repository
from app.integrations.providers import Integrations, get_integrations
from app.models.actions import ActionPlan
from app.models.events import ChangeEventOut
from app.models.impact import ImpactAnalysis
from app.models.planning import DemandForecast, MaterialPlan, ProductionPlan
from app.models.scenario import ScenarioRequest, ScenarioResult
from app.models.sourcing import SourcingResult, SupplierAssessment, SupplierEvidence
from app.services import forecast as forecast_service
from app.services import planning, sourcing
from app.services.actions import build_plan
from app.services.scenario import run_scenario
from app.services.store import DemoStore

EVIDENCE_PARTS = ("performance", "sanctions", "news")


@dataclass
class EventContext:
    repo: Repository
    store: DemoStore
    settings: Settings
    event: ChangeEventOut
    integrations: Integrations = field(default_factory=get_integrations)
    _evidence: dict[str, SupplierEvidence] = field(default_factory=dict)
    _evidence_parts: set[str] = field(default_factory=set)

    @property
    def event_id(self) -> str:
        return self.event.event_id

    # -- impact -----------------------------------------------------------

    def analysis(self, refresh: bool = False) -> ImpactAnalysis:
        if not refresh and self.event_id in self.store.analyses:
            return self.store.analyses[self.event_id]
        from app.api.routes_core import analyze_event  # local import: routes depend on this module

        return analyze_event(self.store, self.repo, self.settings, self.event_id)

    @property
    def part_id(self) -> str:
        return self.analysis().component.part_id

    def product_ids(self) -> list[str]:
        return [p.product_id for p in self.analysis().products]

    def alternative(self) -> str | None:
        return self.event.recommended_alternative_item_id or self.analysis().summary.replacement_part_id

    # -- sourcing ---------------------------------------------------------

    def sourcing(self) -> SourcingResult:
        if self.event_id not in self.store.sourcing:
            self.store.sourcing[self.event_id] = sourcing.find_sourcing_options(
                self.repo.index(), self.integrations, self.part_id, self.product_ids(), self.event_id)
        return self.store.sourcing[self.event_id]

    def evidence(self, part: str) -> list[SupplierEvidence]:
        """Collect one kind of supplier evidence and merge it into the running set."""
        for ev in sourcing.gather_evidence(self.repo.index(), self.integrations, self.sourcing(), (part,)):
            cur = self._evidence.get(ev.supplier_id)
            if cur is None:
                self._evidence[ev.supplier_id] = ev
                continue
            if part == "performance":
                cur.performance = ev.performance
            elif part == "sanctions":
                cur.sanctions_screened, cur.sanctions_hits = True, ev.sanctions_hits
            else:
                cur.news = ev.news
        self._evidence_parts.add(part)
        return list(self._evidence.values())

    def assessment(self) -> SupplierAssessment:
        for part in EVIDENCE_PARTS:
            if part not in self._evidence_parts:
                self.evidence(part)
        result = sourcing.score_candidates(self.repo.index(), self.sourcing(), list(self._evidence.values()),
                                           sourcing.providers_of(self.integrations))
        self.store.assessments[self.event_id] = result
        return result

    def cached_assessment(self) -> SupplierAssessment:
        return self.store.assessments.get(self.event_id) or self.assessment()

    # -- planning ---------------------------------------------------------

    def forecast(self) -> DemandForecast:
        if self.event_id not in self.store.forecasts:
            self.store.forecasts[self.event_id] = forecast_service.forecast_demand(
                self.repo, self.product_ids(), self.settings.demand_horizon_months)
        return self.store.forecasts[self.event_id]

    def materials(self) -> MaterialPlan:
        if self.event_id not in self.store.material_plans:
            self.store.material_plans[self.event_id] = planning.material_plan(self.repo, self.part_id, self.forecast())
        return self.store.material_plans[self.event_id]

    def optimize(self, bridge_buy_qty: int = 0, label: str = "") -> ProductionPlan:
        for existing in self.store.event_plans(self.event_id):
            if existing.inputs.bridge_buy_qty == bridge_buy_qty and existing.status != "REJECTED":
                return existing
        plan = planning.optimize_production(
            self.repo, self.integrations, self.part_id, self.alternative(), bridge_buy_qty,
            plan_id=self.store.next_plan_id(self.event_id), event_id=self.event_id, label=label)
        self.store.save_production_plan(plan)
        return plan

    def propose(self, plan_id: str, note: str) -> ProductionPlan:
        plan = self.store.get_production_plan(plan_id)
        if plan.event_id != self.event_id:
            raise planning.PlanningInputError(f"{plan_id} belongs to another event.")
        for other in self.store.event_plans(self.event_id):
            if other.plan_id != plan_id and other.status == "PROPOSED":
                self.store.set_plan_status(other.plan_id, status="DRAFT")
        return self.store.set_plan_status(plan_id, status="PROPOSED", proposal_note=note)

    def proposed_plan(self) -> ProductionPlan | None:
        plans = self.store.event_plans(self.event_id)
        for status in ("APPROVED", "PROPOSED"):
            match = [p for p in plans if p.status == status]
            if match:
                return match[-1]
        return None

    # -- response ---------------------------------------------------------

    def scenario(self) -> ScenarioResult:
        history = self.store.list_scenarios(self.event_id)
        if history:
            return history[0]
        a = self.analysis()
        req = ScenarioRequest(event_id=self.event_id, replacement_part_id=a.summary.replacement_part_id,
                              margin_threshold=a.summary.margin_threshold)
        result = run_scenario(self.repo, self.part_id, req, self.settings.demand_horizon_months)
        self.store.save_scenario(result)
        return result

    def action_plan(self, rewrite: bool = True) -> ActionPlan:
        plan = build_plan(self.event, self.analysis(), self.scenario(),
                          self.store.assessments.get(self.event_id), self.proposed_plan(), rewrite=rewrite)
        self.store.save_plan(plan)
        return plan

    def numbers_pool(self) -> list[Any]:
        """Everything the agents may quote numbers from."""
        items: list[Any] = [self.event.model_dump(mode="json")]
        if self.event_id in self.store.analyses:
            items.append(self.store.analyses[self.event_id].model_dump(mode="json"))
        for store_dict in (self.store.sourcing, self.store.assessments, self.store.forecasts,
                           self.store.material_plans, self.store.action_plans):
            if self.event_id in store_dict:
                items.append(store_dict[self.event_id].model_dump(mode="json"))
        items += [p.model_dump(mode="json") for p in self.store.event_plans(self.event_id)]
        return items
