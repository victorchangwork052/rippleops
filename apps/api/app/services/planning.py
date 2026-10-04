"""Material requirements and production re-planning (deterministic).

`material_plan` explodes the open work orders into weekly requirements for the
affected component. `optimize_production` re-plans the next 13 weeks with
Google OR-Tools CP-SAT:

* decide how many units of each product to build, on which line, each week;
* decide which units use the affected component and which use the
  alternative (only where, and from when, the alternative is approved);
* respect line capacity, the finite component supply (plus an optional bridge
  buy) and the alternative's early supply until its lead time has passed;
* maximize gross margin, minus a penalty for every unit-week of lateness
  (doubled for strategic customers).

`baseline_plan` simulates the current schedule with no response, for comparison.
The solver is single-threaded with a deterministic time limit, so the same
inputs always give the same plan.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.db.repository import Repository
from app.integrations.providers import Integrations
from app.models.planning import (
    DemandForecast,
    LineWeekLoad,
    MaterialPlan,
    MaterialWeek,
    PlanChange,
    PlanInputs,
    PlanKpis,
    ProductionPlan,
    ProductPlanRow,
    ScheduleCell,
    SolverInfo,
)
from app.services.costing import CostEngine, CostParams

LATE_PENALTY_SHARE = 0.04  # of selling price, per unit per week late
STRATEGIC_MULTIPLIER = 2
BRIDGE_INSPECTION_DAYS = 14
SOLVER_DETERMINISTIC_TIME = 5.0
SOLVER_GAP = 0.0005  # stop once within 0.05% of the proven optimum


class PlanningInputError(ValueError):
    pass


@dataclass
class PlanningData:
    part_id: str
    weeks: list[date]
    products: list[str]
    affected: set[str]
    names: dict[str, str]
    demand: dict[tuple[str, int], float]
    strategic: set[str]
    hours: dict[str, dict[str, float]]  # product -> line -> hours per unit
    primary: dict[str, str]
    capacity: dict[str, float]
    line_names: dict[str, str]
    usage: dict[str, float]  # component units per product unit (affected only)
    price: dict[str, float]
    margin_original: dict[str, float]
    margin_alternative: dict[str, float] = field(default_factory=dict)
    alternative_week: dict[str, int] = field(default_factory=dict)  # first week index the alternative may be used


def load_planning_data(repo: Repository, part_id: str, alternative: str | None) -> PlanningData:
    index = repo.index()
    snap = index.snapshot
    if not snap.work_orders:
        raise PlanningInputError("No work orders are available to plan.")
    weeks = sorted({w.planned_week for w in snap.work_orders})
    wpos = {w: i for i, w in enumerate(weeks)}
    demand: dict[tuple[str, int], float] = defaultdict(float)
    strategic: set[str] = set()
    for wo in snap.work_orders:
        demand[(wo.product_id, wpos[wo.planned_week])] += wo.quantity
        if wo.customer_priority == "STRATEGIC":
            strategic.add(wo.product_id)
    products = sorted({wo.product_id for wo in snap.work_orders})
    hours: dict[str, dict[str, float]] = defaultdict(dict)
    primary: dict[str, str] = {}
    for r in snap.product_routings:
        hours[r.product_id][r.line_id] = r.hours_per_unit
        if r.routing_type == "PRIMARY":
            primary[r.product_id] = r.line_id
    usage = {u.product_id: u.effective_component_qty for u in repo.trace(part_id).products}
    base = CostEngine(index)
    price = {p: index.selling_price[p] for p in products}
    data = PlanningData(
        part_id=part_id, weeks=weeks, products=products, affected=set(usage) & set(products),
        names={p: index.item_name(p) for p in products}, demand=dict(demand), strategic=strategic,
        hours=dict(hours), primary=primary,
        capacity={line.line_id: line.weekly_capacity_hours for line in snap.production_lines},
        line_names={line.line_id: line.line_name for line in snap.production_lines},
        usage=usage, price=price, margin_original={p: price[p] - base.cost(p).total for p in products})
    if alternative and alternative in index.items:
        alt_engine = CostEngine(index, CostParams(substitutions={part_id: alternative}))
        for p in data.affected:
            approval = index.approval_for(part_id, alternative, p)
            if approval is None or approval.approval_status == "NOT_APPROVED":
                continue
            data.margin_alternative[p] = price[p] - alt_engine.cost(p).total
            data.alternative_week[p] = (0 if approval.approval_status == "APPROVED"
                                        else math.ceil(approval.qualification_lead_time_days / 7))
    return data


# -- material requirements ----------------------------------------------------


def material_plan(repo: Repository, part_id: str, forecast: DemandForecast | None = None) -> MaterialPlan:
    data = load_planning_data(repo, part_id, None)
    available = repo.index().available_qty.get(part_id, 0.0)
    ratio: dict[tuple[str, str], float] = {}
    if forecast:
        for p in forecast.products:
            for pt in p.points:
                ratio[(p.product_id, pt.month[:7])] = pt.forecast_qty / pt.plan_qty if pt.plan_qty else 1.0
    weeks, left, left_fc = [], available, available
    stockout = stockout_fc = None
    per_product: dict[str, float] = defaultdict(float)
    total = 0.0
    for wi, wk in enumerate(data.weeks):
        req = req_fc = 0.0
        for p in data.affected:
            qty = data.demand.get((p, wi), 0.0) * data.usage[p]
            req += qty
            req_fc += round(qty * ratio.get((p, wk.isoformat()[:7]), 1.0))
            per_product[p] += qty
        total += req
        left -= req
        left_fc -= req_fc
        if left < 0 and stockout is None:
            stockout = wk.isoformat()
        if left_fc < 0 and stockout_fc is None:
            stockout_fc = wk.isoformat()
        weeks.append(MaterialWeek(week=wk.isoformat(), requirement=req, requirement_forecast=req_fc,
                                  projected_available=left, projected_available_forecast=left_fc))
    return MaterialPlan(part_id=part_id, available_qty=available, weeks=weeks, total_requirement=total,
                        stockout_week=stockout, stockout_week_forecast=stockout_fc,
                        products=dict(sorted(per_product.items())))


# -- plans ----------------------------------------------------------------


@dataclass
class _Solution:
    build: dict[tuple[str, str, int], float]  # (product, line, week) -> units
    alt: dict[tuple[str, int], float]  # (product, week) -> units using the alternative


def _kpis(d: PlanningData, s: _Solution, supply: float, bridge_premium: float = 0.0) -> PlanKpis:
    built: dict[str, float] = defaultdict(float)
    by_week: dict[tuple[str, int], float] = defaultdict(float)
    for (p, _, w), q in s.build.items():
        built[p] += q
        by_week[(p, w)] += q
    alt_by_p: dict[str, float] = defaultdict(float)
    for (p, _), q in s.alt.items():
        alt_by_p[p] += q
    demand = {p: sum(d.demand.get((p, w), 0.0) for w in range(len(d.weeks))) for p in d.products}
    late = 0.0
    for p in d.products:
        cum_d = cum_b = 0.0
        for w in range(len(d.weeks)):
            cum_d += d.demand.get((p, w), 0.0)
            cum_b += by_week.get((p, w), 0.0)
            late += cum_d - cum_b
    margin = sum((built[p] - alt_by_p[p]) * d.margin_original[p]
                 + alt_by_p[p] * d.margin_alternative.get(p, d.margin_original[p]) for p in d.products)
    used = sum((built[p] - alt_by_p[p]) * d.usage[p] for p in d.affected)
    alt_used = sum(alt_by_p[p] * d.usage[p] for p in d.affected)

    def fill(ps) -> float:
        dem = sum(demand[p] for p in ps)
        return round(sum(built[p] for p in ps) / dem, 4) if dem else 1.0

    total_d = sum(demand.values())
    total_b = sum(built.values())
    return PlanKpis(
        demand_units=total_d, built_units=total_b, unmet_units=total_d - total_b, fill_rate=fill(d.products),
        affected_fill_rate=fill(d.affected), strategic_fill_rate=fill([p for p in d.products if p in d.strategic]),
        late_unit_weeks=late, gross_margin=round(margin - bridge_premium, 2), bridge_premium=round(bridge_premium, 2),
        component_used=used, component_supply=supply,
        component_remaining=supply - used, alternative_used=alt_used)


def _line_loads(d: PlanningData, s: _Solution) -> list[LineWeekLoad]:
    hours: dict[tuple[str, int], float] = defaultdict(float)
    for (p, line, w), q in s.build.items():
        hours[(line, w)] += q * d.hours[p][line]
    out = []
    for line in sorted(d.capacity):
        for w, wk in enumerate(d.weeks):
            h = round(hours.get((line, w), 0.0), 1)
            cap = d.capacity[line]
            out.append(LineWeekLoad(line_id=line, week=wk.isoformat(), capacity_hours=cap, planned_hours=h,
                                    utilization=round(h / cap, 4) if cap else 0.0))
    return out


def _as_scheduled(d: PlanningData) -> _Solution:
    """The work orders exactly as scheduled, on their primary lines (may exceed capacity)."""
    return _Solution(build={(p, d.primary[p], w): q for (p, w), q in d.demand.items() if q > 0}, alt={})


def baseline_plan(d: PlanningData, supply: float) -> _Solution:
    """Current schedule with no response: primary lines only, no alternative,
    late units carried forward, the component consumed until it runs out."""
    backlog: dict[str, float] = defaultdict(float)
    build: dict[tuple[str, str, int], float] = {}
    left = supply
    for w in range(len(d.weeks)):
        for p in d.products:
            backlog[p] += d.demand.get((p, w), 0.0)
        for line in sorted(d.capacity):
            cap = d.capacity[line]
            members = sorted((p for p in d.products if d.primary[p] == line),
                             key=lambda p: (p not in d.strategic, p))
            for p in members:
                q = backlog[p]
                if p in d.affected and d.usage[p]:
                    q = min(q, math.floor(left / d.usage[p]))
                q = min(q, math.floor(cap / d.hours[p][line]))
                if q <= 0:
                    continue
                build[(p, line, w)] = float(q)
                backlog[p] -= q
                cap -= q * d.hours[p][line]
                if p in d.affected:
                    left -= q * d.usage[p]
    return _Solution(build=build, alt={})


def solve_plan(d: PlanningData, on_hand: float, bridge_qty: int, bridge_week: int | None,
               alt_early_supply: float, alt_lead_weeks: int) -> tuple[_Solution, SolverInfo]:
    from ortools.sat.python import cp_model

    m = cp_model.CpModel()
    W = len(d.weeks)
    total_demand = {p: int(sum(d.demand.get((p, w), 0.0) for w in range(W))) for p in d.products}
    x: dict[tuple[str, str, int], cp_model.IntVar] = {}
    u: dict[tuple[str, int], cp_model.IntVar] = {}
    for p in d.products:
        for line in d.hours[p]:
            for w in range(W):
                x[(p, line, w)] = m.new_int_var(0, total_demand[p], f"x_{p}_{line}_{w}")
        if p in d.alternative_week:
            for w in range(d.alternative_week[p], W):
                u[(p, w)] = m.new_int_var(0, total_demand[p], f"u_{p}_{w}")

    def built(p: str, w: int):
        return sum(x[(p, line, w)] for line in d.hours[p])

    for p in d.products:
        cum_d = 0
        for w in range(W):
            cum_d += int(d.demand.get((p, w), 0.0))
            m.add(sum(built(p, t) for t in range(w + 1)) <= cum_d)  # no building ahead of demand
            if (p, w) in u:
                m.add(u[(p, w)] <= built(p, w))
    for line, cap in d.capacity.items():
        for w in range(W):
            terms = [round(d.hours[p][line] * 100) * x[(p, line, w)] for p in d.products if line in d.hours[p]]
            if terms:
                m.add(sum(terms) <= round(cap * 100))

    usage = {p: round(d.usage[p] * 100) for p in d.affected}
    for w in range(W):
        supply = on_hand + (bridge_qty if bridge_week is not None and w >= bridge_week else 0)
        m.add(sum(usage[p] * (built(p, t) - u.get((p, t), 0)) for p in d.affected for t in range(w + 1))
              <= round(supply * 100))
        if w < alt_lead_weeks and u:
            m.add(sum(usage[p] * u[(p, t)] for (p, t) in u if t <= w) <= round(alt_early_supply * 100))

    objective = []
    for (p, _line, w), var in x.items():
        penalty = d.price[p] * LATE_PENALTY_SHARE * (STRATEGIC_MULTIPLIER if p in d.strategic else 1)
        # Building in week w removes (W - w) unit-weeks of lateness versus never building.
        objective.append(round((d.margin_original[p] + penalty * (W - w)) * 100) * var)
    for (p, _w), var in u.items():
        objective.append(round((d.margin_alternative[p] - d.margin_original[p]) * 100) * var)
    m.maximize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 7
    solver.parameters.max_deterministic_time = SOLVER_DETERMINISTIC_TIME
    solver.parameters.relative_gap_limit = SOLVER_GAP
    started = time.perf_counter()
    status = solver.solve(m)
    elapsed = int((time.perf_counter() - started) * 1000)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise PlanningInputError("The production plan could not be solved with these inputs.")
    build = {k: float(solver.value(v)) for k, v in x.items() if solver.value(v) > 0}
    alt = {k: float(solver.value(v)) for k, v in u.items() if solver.value(v) > 0}
    proto = m.proto
    info = SolverInfo(name="Google OR-Tools CP-SAT", status=solver.status_name(status),
                      objective=round(solver.objective_value / 100, 2), variables=len(proto.variables),
                      constraints=len(proto.constraints), solve_ms=elapsed, gap_limit=SOLVER_GAP)
    return _Solution(build=build, alt=alt), info


def _schedule(d: PlanningData, s: _Solution) -> list[ScheduleCell]:
    """Schedule cells; alternative-part units are shown on the primary line first."""
    left = dict(s.alt)
    cells = []
    order = sorted(s.build.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1] != d.primary[kv[0][0]]))
    for (p, line, w), q in order:
        a = min(q, left.get((p, w), 0.0))
        left[(p, w)] = left.get((p, w), 0.0) - a
        cells.append(ScheduleCell(product_id=p, line_id=line, week=d.weeks[w].isoformat(), qty=q, alternative_qty=a))
    return cells


def _fmt_week(d: date) -> str:
    return f"{d:%b} {d.day}"


def _changes(d: PlanningData, s: _Solution, alternative: str | None, bridge_qty: int,
             bridge_week: date | None) -> list[PlanChange]:
    out: list[PlanChange] = []
    built: dict[str, float] = defaultdict(float)
    flex: dict[str, float] = defaultdict(float)
    alt_units: dict[str, float] = defaultdict(float)
    alt_first: dict[str, int] = {}
    for (p, line, _), q in s.build.items():
        built[p] += q
        if line != d.primary[p]:
            flex[p] += q
    for (p, w), q in s.alt.items():
        alt_units[p] += q
        alt_first[p] = min(alt_first.get(p, w), w)
    if bridge_qty:
        out.append(PlanChange(kind="BRIDGE_BUY", product_ids=[], units=bridge_qty,
                              description=f"Buy {bridge_qty:,} units of {d.part_id} from broker stock, available "
                                          f"for production from the week of {_fmt_week(bridge_week)}."
                              if bridge_week else f"Buy {bridge_qty:,} units of {d.part_id} from broker stock."))
    if alternative:
        groups: dict[int, list[str]] = defaultdict(list)
        for p in sorted(alt_units):
            groups[alt_first[p]].append(p)
        for w, ps in sorted(groups.items()):
            units = sum(alt_units[p] for p in ps)
            out.append(PlanChange(kind="SWITCH_COMPONENT", product_ids=ps, units=units,
                                  description=f"Build {units:,.0f} units of {', '.join(ps)} with {alternative} "
                                              f"from the week of {_fmt_week(d.weeks[w])}."))
    reserve = [p for p in sorted(d.affected) if p not in d.alternative_week and built[p] > 0]
    if reserve:
        units = sum((built[p] - alt_units[p]) * d.usage[p] for p in reserve)
        out.append(PlanChange(kind="RESERVE_STOCK", product_ids=reserve, units=units,
                              description=f"Reserve {units:,.0f} units of {d.part_id} for {', '.join(reserve)}, "
                                          f"which have no approved alternative yet."))
    moves: dict[tuple[str, str], list[str]] = defaultdict(list)
    for p in flex:
        alt_line = next(line for line in d.hours[p] if line != d.primary[p])
        moves[(d.primary[p], alt_line)].append(p)
    for (src, dst), ps in sorted(moves.items(), key=lambda kv: -sum(flex[p] for p in kv[1])):
        ps.sort(key=lambda p: (-flex[p], p))
        units = sum(flex[p] for p in ps)
        names = ", ".join(ps[:4]) + (f" and {len(ps) - 4} more" if len(ps) > 4 else "")
        out.append(PlanChange(kind="MOVE_LINE", product_ids=ps, units=units,
                              description=f"Move {units:,.0f} units ({names}) from {d.line_names[src]} to "
                                          f"{d.line_names[dst]} to relieve the capacity overload."))
    for p in sorted(d.products):
        unmet = sum(d.demand.get((p, w), 0.0) for w in range(len(d.weeks))) - built[p]
        if unmet > 0 and p in d.affected:
            units = "unit" if unmet == 1 else "units"
            out.append(PlanChange(kind="UNMET_DEMAND", product_ids=[p], units=unmet,
                                  description=f"{unmet:,.0f} {units} of {p} cannot be built within the plan horizon."))
    return out


def optimize_production(repo: Repository, integrations: Integrations, part_id: str, alternative: str | None,
                        bridge_buy_qty: int = 0, plan_id: str = "PLAN", event_id: str | None = None,
                        label: str = "") -> ProductionPlan:
    if bridge_buy_qty < 0:
        raise PlanningInputError("The bridge-buy quantity cannot be negative.")
    index = repo.index()
    d = load_planning_data(repo, part_id, alternative)
    on_hand = index.available_qty.get(part_id, 0.0)

    # Bridge stock arrives after the broker lead time plus incoming inspection.
    broker = [o for o in integrations.catalog.offers(part_id) if o.channel == "BROKER"]
    bridge_days = (broker[0].lead_time_days if broker else 14) + BRIDGE_INSPECTION_DAYS
    bridge_date = index.as_of + timedelta(days=bridge_days)
    bridge_week = next((i for i, wk in enumerate(d.weeks) if wk >= bridge_date), None) if bridge_buy_qty else None
    if bridge_buy_qty and broker and bridge_buy_qty > broker[0].stock:
        raise PlanningInputError(f"Broker stock is limited to {broker[0].stock:,} units.")

    alt_early = alt_lead = 0
    if alternative and d.alternative_week:
        alt_early = index.available_qty.get(alternative, 0.0) + sum(
            o.stock for o in integrations.catalog.offers(alternative) if o.channel == "AUTHORIZED")
        sp = index.supplier_part.get(alternative)
        alt_lead = math.ceil(sp.lead_time_days / 7) if sp else 0

    solution, info = solve_plan(d, on_hand, bridge_buy_qty, bridge_week, alt_early, alt_lead)
    base = baseline_plan(d, on_hand)
    supply = on_hand + bridge_buy_qty
    std = index.supplier_part.get(part_id)
    premium = bridge_buy_qty * max(0.0, broker[0].unit_price - std.current_unit_price) if broker and std else 0.0

    rows = []
    for p in d.products:
        b = sum(q for (pp, _, _), q in solution.build.items() if pp == p)
        a = sum(q for (pp, _), q in solution.alt.items() if pp == p)
        on_alt_line = sum(q for (pp, line, _), q in solution.build.items() if pp == p and line != d.primary[p])
        dem = sum(d.demand.get((p, w), 0.0) for w in range(len(d.weeks)))
        aw = d.alternative_week.get(p)
        rows.append(ProductPlanRow(
            product_id=p, name=d.names[p], affected=p in d.affected, strategic=p in d.strategic,
            primary_line=d.primary[p], demand=dem,
            baseline_built=sum(q for (pp, _, _), q in base.build.items() if pp == p), built=b,
            built_with_original=b - a, built_with_alternative=a, built_on_alternate_line=on_alt_line,
            unmet=dem - b, alternative_from_week=d.weeks[aw].isoformat() if aw is not None and aw < len(d.weeks)
            else None, unit_margin_original=round(d.margin_original[p], 2),
            unit_margin_alternative=round(d.margin_alternative[p], 2) if p in d.margin_alternative else None))
    rows.sort(key=lambda r: (not r.affected, r.product_id))

    return ProductionPlan(
        plan_id=plan_id, event_id=event_id, label=label or ("With bridge buy" if bridge_buy_qty else "Optimized plan"),
        weeks=[w.isoformat() for w in d.weeks],
        inputs=PlanInputs(part_id=part_id, alternative_part_id=alternative if d.alternative_week else None,
                          bridge_buy_qty=bridge_buy_qty,
                          bridge_arrival_week=d.weeks[bridge_week].isoformat() if bridge_week is not None else None,
                          component_on_hand=on_hand, alternative_early_supply=alt_early,
                          alternative_lead_time_weeks=alt_lead),
        solver=info, baseline=_kpis(d, base, on_hand), optimized=_kpis(d, solution, supply, premium), products=rows,
        schedule=_schedule(d, solution),
        line_loads=_line_loads(d, solution), baseline_line_loads=_line_loads(d, _as_scheduled(d)), lines=d.line_names,
        changes=_changes(d, solution, alternative if d.alternative_week else None, bridge_buy_qty,
                         d.weeks[bridge_week] if bridge_week is not None else None))
