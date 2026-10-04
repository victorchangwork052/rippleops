"""Alternative sourcing and supplier scorecards (deterministic).

`find_sourcing_options` merges the internal approved-vendor list (alternate
parts + supplier parts) with distributor cross-references. `gather_evidence`
collects supplier KPIs, sanctions screening and news. `score_candidates`
turns the evidence into a weighted 0-100 scorecard. Agents decide which of
these to call and explain the result; they never produce the scores.
"""

from __future__ import annotations

from app.integrations.providers import Integrations
from app.models.sourcing import (
    NewsItem,
    PerformanceSnapshot,
    SanctionsHit,
    Scorecard,
    ScoreComponent,
    SourcingCandidate,
    SourcingResult,
    SupplierAssessment,
    SupplierEvidence,
)
from app.services.index import DataIndex

WEIGHTS = {"Delivery": 25.0, "Quality": 20.0, "Lead time": 15.0, "Cost": 15.0, "Supply risk": 15.0,
           "Qualification": 10.0}
PREFERRED_SCORE = 70.0
VIABLE_SCORE = 50.0
NO_HISTORY_SHARE = 0.4  # new suppliers get 40% of the delivery / quality weight
EXTERNAL_QUALIFICATION_DAYS = {"FUNCTIONAL_EQUIVALENT": 150, "PIN_TO_PIN_CLONE": 120, "DIRECT_SUCCESSOR": 90}
BROKER_INSPECTION_DAYS = 14
RISK_BASE = {"LOW": 15.0, "MEDIUM": 11.0, "HIGH": 8.0}
UNKNOWN_RISK_BASE = 9.0
NEWS_POINTS = {"HIGH": -4.0, "MEDIUM": -1.5, "LOW": -0.5, "POSITIVE": 1.0}
BROKER_RISK = -4.0
DECLINING_TREND_RISK = -1.5


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _r1(x: float) -> float:
    return round(x + 0.0, 1)


def find_sourcing_options(index: DataIndex, integrations: Integrations, part_id: str, product_ids: list[str],
                          event_id: str | None = None) -> SourcingResult:
    catalog = integrations.catalog
    current = index.supplier_part.get(part_id)
    current_price = current.current_unit_price if current else 0.0
    current_supplier = index.suppliers.get(current.supplier_id) if current else None
    candidates: list[SourcingCandidate] = []

    def delta(price: float) -> float:
        return round(price / current_price - 1, 4) if current_price else 0.0

    # 1) Internal approved-vendor list.
    internal_ids = index.alternative_ids(part_id)
    for alt in internal_ids:
        sp = index.supplier_part.get(alt)
        sup = index.suppliers.get(sp.supplier_id) if sp else None
        if sp is None or sup is None:
            continue
        approvals = {pid: index.approval_for(part_id, alt, pid) for pid in product_ids}
        approved = [pid for pid, a in approvals.items() if a and a.approval_status == "APPROVED"]
        validating = sorted(pid for pid, a in approvals.items() if not a or a.approval_status != "APPROVED")
        default = index.approval_for(part_id, alt, "")
        status = default.approval_status if default else "NOT_APPROVED"
        qual = max((a.qualification_lead_time_days for a in approvals.values() if a), default=0)
        xref = next((x for x in catalog.cross_references(part_id) if x.mpn == alt), None)
        stock = sum(o.stock for o in catalog.offers(alt))
        candidates.append(SourcingCandidate(
            candidate_id=f"{alt}@{sup.supplier_id}", part_id=alt, manufacturer=sup.supplier_name,
            supplier_id=sup.supplier_id, supplier_name=sup.supplier_name, country=sup.country,
            source="INTERNAL_AVL", channel="MANUFACTURER",
            match_type=xref.match_type if xref else "DIRECT_SUCCESSOR",
            pin_compatible=xref.pin_compatible if xref else False, is_new_supplier=False,
            approval_status=status, products_approved=len(approved), products_needing_validation=validating,
            qualification_lead_time_days=qual, unit_price=sp.current_unit_price,
            price_delta_pct=delta(sp.current_unit_price), lead_time_days=sp.lead_time_days,
            available_stock=stock or None,
            notes=(default.notes if default else "") + (f" Distributor stock: {stock:,} units." if stock else "")))

    # 2) Distributor cross-references not already on the approved-vendor list.
    for x in catalog.cross_references(part_id):
        if x.mpn in internal_ids:
            continue
        maker = catalog.manufacturer(x.manufacturer)
        offers = catalog.offers(x.mpn)
        if maker is None or not offers:
            continue
        best = min(offers, key=lambda o: o.unit_price)
        candidates.append(SourcingCandidate(
            candidate_id=f"{x.mpn}@{maker.supplier_id}", part_id=x.mpn, manufacturer=maker.name,
            supplier_id=maker.supplier_id, supplier_name=maker.name, country=maker.country,
            source="DISTRIBUTOR_CATALOG", channel=best.channel, match_type=x.match_type,
            pin_compatible=x.pin_compatible, is_new_supplier=maker.supplier_id not in index.suppliers,
            approval_status="NOT_QUALIFIED", products_approved=0, products_needing_validation=sorted(product_ids),
            qualification_lead_time_days=EXTERNAL_QUALIFICATION_DAYS.get(x.match_type, 150),
            unit_price=best.unit_price, price_delta_pct=delta(best.unit_price), lead_time_days=best.lead_time_days,
            available_stock=sum(o.stock for o in offers), notes=f"{x.notes} Offered by {best.distributor}."))

    # 3) The affected part itself from non-franchised channels (bridge stock).
    for o in catalog.offers(part_id):
        candidates.append(SourcingCandidate(
            candidate_id=f"{part_id}@{o.supplier_id}", part_id=part_id,
            manufacturer=current_supplier.supplier_name if current_supplier else "",
            supplier_id=o.supplier_id, supplier_name=o.distributor, country=o.country, source="DISTRIBUTOR_CATALOG",
            channel=o.channel, match_type="SAME_PART", pin_compatible=True,
            is_new_supplier=o.supplier_id not in index.suppliers, approval_status="APPROVED",
            products_approved=len(product_ids), products_needing_validation=[],
            qualification_lead_time_days=BROKER_INSPECTION_DAYS if o.channel == "BROKER" else 0,
            unit_price=o.unit_price, price_delta_pct=delta(o.unit_price), lead_time_days=o.lead_time_days,
            available_stock=o.stock, notes=f"{o.notes} Date code {o.date_code}."))

    return SourcingResult(
        event_id=event_id, part_id=part_id, part_name=index.item_name(part_id),
        current_supplier=current_supplier.supplier_name if current_supplier else None,
        current_unit_price=current_price, affected_products=len(product_ids),
        catalog_provider=catalog.provider, candidates=candidates)


def supplier_performance(index: DataIndex, supplier_id: str) -> PerformanceSnapshot | None:
    rows = sorted((r for r in index.snapshot.supplier_performance if r.supplier_id == supplier_id),
                  key=lambda r: r.quarter_end)
    if not rows:
        return None
    n = len(rows)
    return PerformanceSnapshot(
        quarters=n,
        on_time_delivery_rate=round(sum(r.on_time_delivery_rate for r in rows) / n, 4),
        quality_ppm=round(sum(r.quality_ppm for r in rows) / n, 1),
        avg_lead_time_days=round(sum(r.avg_lead_time_days for r in rows) / n, 1),
        lead_time_variance_days=round(sum(r.lead_time_variance_days for r in rows) / n, 1),
        on_time_trend_points=round((rows[-1].on_time_delivery_rate - rows[0].on_time_delivery_rate) * 100, 1))


def screen_supplier(integrations: Integrations, names: list[str]) -> list[SanctionsHit]:
    hits: dict[str, SanctionsHit] = {}
    for name in names:
        for h in integrations.sanctions.screen(name):
            hits[h.entity_id] = SanctionsHit(entity_id=h.entity_id, listed_name=h.listed_name,
                                             list_name=h.list_name, program=h.program, listed_on=h.listed_on)
    return list(hits.values())


def supplier_news(integrations: Integrations, name: str) -> list[NewsItem]:
    return [NewsItem(date=a.date, category=a.category, severity=a.severity, source=a.source,
                     headline=a.headline, summary=a.summary) for a in integrations.news.search(name)]


def _screen_names(c: SourcingCandidate) -> list[str]:
    names = [c.supplier_name]
    if " Offered by " in c.notes:  # also screen the distributor that sells the part
        names.append(c.notes.split(" Offered by ", 1)[1].rstrip("."))
    return names


def gather_evidence(index: DataIndex, integrations: Integrations, sourcing: SourcingResult,
                    parts: tuple[str, ...] = ("performance", "sanctions", "news")) -> list[SupplierEvidence]:
    out: dict[str, SupplierEvidence] = {}
    for c in sourcing.candidates:
        ev = out.get(c.supplier_id) or SupplierEvidence(
            supplier_id=c.supplier_id, supplier_name=c.supplier_name, performance=None,
            sanctions_screened=False, sanctions_hits=[], news=[])
        if "performance" in parts:
            ev.performance = supplier_performance(index, c.supplier_id)
        if "sanctions" in parts:
            ev.sanctions_screened = True
            known = {h.entity_id for h in ev.sanctions_hits}
            hits = screen_supplier(integrations, _screen_names(c))
            ev.sanctions_hits += [h for h in hits if h.entity_id not in known]
        if "news" in parts:
            ev.news = supplier_news(integrations, c.supplier_name)
        out[c.supplier_id] = ev
    return list(out.values())


def _score(c: SourcingCandidate, ev: SupplierEvidence, risk_level: str | None) -> Scorecard:
    comps: list[ScoreComponent] = []
    flags: list[str] = []
    perf = ev.performance

    w = WEIGHTS["Delivery"]
    if perf:
        comps.append(ScoreComponent(criterion="Delivery", weight=w,
                                    score=_r1(w * _clamp((perf.on_time_delivery_rate - 0.75) / 0.22)),
                                    evidence=f"On-time delivery {perf.on_time_delivery_rate * 100:.1f}% "
                                             f"over {perf.quarters} quarters"))
    else:
        comps.append(ScoreComponent(criterion="Delivery", weight=w, score=_r1(w * NO_HISTORY_SHARE),
                                    evidence="No delivery history with this supplier"))
    w = WEIGHTS["Quality"]
    if perf:
        comps.append(ScoreComponent(criterion="Quality", weight=w, score=_r1(w * _clamp(1 - perf.quality_ppm / 600)),
                                    evidence=f"{perf.quality_ppm:,.0f} defective parts per million"))
    else:
        comps.append(ScoreComponent(criterion="Quality", weight=w, score=_r1(w * NO_HISTORY_SHARE),
                                    evidence="No incoming-quality history with this supplier"))
    w = WEIGHTS["Lead time"]
    comps.append(ScoreComponent(criterion="Lead time", weight=w,
                                score=_r1(w * _clamp(1 - (c.lead_time_days - 14) / 154)),
                                evidence=f"Quoted lead time {c.lead_time_days} days"))
    w = WEIGHTS["Cost"]
    comps.append(ScoreComponent(criterion="Cost", weight=w,
                                score=_r1(w * _clamp(1 - max(0.0, c.price_delta_pct) / 0.5)),
                                evidence=f"Unit price ${c.unit_price:,.2f} "
                                         f"({c.price_delta_pct * 100:+.1f}% vs. current)"))

    w = WEIGHTS["Supply risk"]
    risk = RISK_BASE.get(risk_level or "", UNKNOWN_RISK_BASE)
    notes = [f"supplier risk rating {risk_level.lower()}" if risk_level else "no internal risk rating"]
    if c.channel == "BROKER":
        risk += BROKER_RISK
        notes.append("non-franchised broker channel")
    for n in ev.news:
        risk += NEWS_POINTS[n.severity]
    if ev.news:
        worst = ev.news[0]
        notes.append(f"{len(ev.news)} news item(s), most severe: {worst.severity.lower()}")
    if perf and perf.on_time_trend_points <= -5:
        risk += DECLINING_TREND_RISK
        notes.append(f"on-time delivery down {abs(perf.on_time_trend_points):.1f} points")
    comps.append(ScoreComponent(criterion="Supply risk", weight=w, score=_r1(max(0.0, min(w, risk))),
                                evidence="; ".join(notes).capitalize()))

    w = WEIGHTS["Qualification"]
    if c.approval_status == "APPROVED":
        total = c.products_approved + len(c.products_needing_validation)
        share = (c.products_approved + 0.5 * len(c.products_needing_validation)) / total if total else 1.0
        qual = w * share
        qual_ev = (f"Approved for {c.products_approved} products; {len(c.products_needing_validation)} need "
                   f"validation" if c.products_needing_validation else "Approved for all affected products")
    elif c.approval_status == "NOT_APPROVED":
        qual, qual_ev = w * 0.2, f"Not approved; qualification about {c.qualification_lead_time_days} days"
    else:
        qual = w * (0.1 if c.pin_compatible else 0.0)
        qual_ev = f"Not qualified; qualification about {c.qualification_lead_time_days} days"
    comps.append(ScoreComponent(criterion="Qualification", weight=w, score=_r1(qual), evidence=qual_ev))

    total = _r1(sum(x.score for x in comps))
    if c.is_new_supplier:
        flags.append("New supplier: onboarding audit required")
    if c.channel == "BROKER":
        flags.append("Broker stock: require traceability documents and incoming inspection")
    if c.match_type in ("FUNCTIONAL_EQUIVALENT", "PIN_TO_PIN_CLONE") and c.approval_status != "APPROVED":
        flags.append("Engineering qualification required before production use")
    if ev.sanctions_hits:
        hit = ev.sanctions_hits[0]
        flags.insert(0, f"Compliance block: matches {hit.listed_name} on the {hit.list_name}")
        tier, total = "BLOCKED", 0.0
    elif c.match_type == "SAME_PART" and c.channel == "BROKER":
        tier = "BRIDGE_ONLY"
    elif total >= PREFERRED_SCORE:
        tier = "PREFERRED"
    elif total >= VIABLE_SCORE:
        tier = "VIABLE"
    else:
        tier = "NOT_RECOMMENDED"
    return Scorecard(candidate_id=c.candidate_id, part_id=c.part_id, supplier_name=c.supplier_name,
                     total_score=total, tier=tier, components=comps, flags=flags)


def score_candidates(index: DataIndex, sourcing: SourcingResult, evidence: list[SupplierEvidence],
                     providers: dict[str, str]) -> SupplierAssessment:
    by_supplier = {e.supplier_id: e for e in evidence}
    cards = []
    for c in sourcing.candidates:
        ev = by_supplier.get(c.supplier_id) or SupplierEvidence(
            supplier_id=c.supplier_id, supplier_name=c.supplier_name, performance=None,
            sanctions_screened=False, sanctions_hits=[], news=[])
        sup = index.suppliers.get(c.supplier_id)
        cards.append(_score(c, ev, sup.risk_level if sup else None))
    cand = {c.candidate_id: c for c in sourcing.candidates}
    usable = [s for s in cards if s.tier != "BLOCKED"]
    ranked = sorted(usable, key=lambda s: -s.total_score)
    transition = [s for s in ranked if cand[s.candidate_id].approval_status == "APPROVED"
                  and cand[s.candidate_id].match_type != "SAME_PART"]
    recommended = transition[0].candidate_id if transition else None
    second = next((s.candidate_id for s in ranked if s.candidate_id != recommended
                   and s.tier in ("PREFERRED", "VIABLE") and cand[s.candidate_id].match_type != "SAME_PART"), None)
    bridge = next((s.candidate_id for s in ranked if s.tier == "BRIDGE_ONLY"), None)
    return SupplierAssessment(
        event_id=sourcing.event_id, part_id=sourcing.part_id, weights=WEIGHTS, evidence=evidence,
        scorecards=sorted(cards, key=lambda s: -s.total_score), recommended_candidate_id=recommended,
        second_source_candidate_id=second, bridge_candidate_id=bridge,
        blocked_candidate_ids=[s.candidate_id for s in cards if s.tier == "BLOCKED"], providers=providers)


def providers_of(integrations: Integrations) -> dict[str, str]:
    return {"internal": "RippleOps product data (BigQuery)", "catalog": integrations.catalog.provider,
            "sanctions": integrations.sanctions.provider, "news": integrations.news.provider}
