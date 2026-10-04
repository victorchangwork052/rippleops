"""Statistical demand forecast, compared with the demand plan.

With DATA_BACKEND=bigquery the forecast comes from BigQuery ML `AI.FORECAST`
(Google's TimesFM foundation model) over the shipment history. Locally, a
deterministic seasonal-trend method is used. Either way the numbers come from
a forecasting model, never from Gemini.
"""

from __future__ import annotations

import logging
from datetime import date

from app.db.repository import Repository
from app.models.planning import DemandForecast, ForecastPoint, HistoryPoint, ProductForecast
from app.services.demand import horizon_months

log = logging.getLogger("rippleops.forecast")
CONFIDENCE = 0.8
Z80 = 1.2816


def _season_index(history: list[tuple[date, float]]) -> dict[int, float]:
    """Average ratio of each calendar month to its 12-month centred mean."""
    by_month: dict[int, list[float]] = {}
    qty = [q for _, q in history]
    for i in range(6, len(history) - 6):
        window = qty[i - 6:i + 6]
        mean = sum(window) / 12
        if mean > 0:
            by_month.setdefault(history[i][0].month, []).append(qty[i] / mean)
    idx = {m: sum(v) / len(v) for m, v in by_month.items()}
    norm = sum(idx.values()) / len(idx) if idx else 1.0
    return {m: idx.get(m, norm) / norm for m in range(1, 13)}


def seasonal_trend(history: list[tuple[date, float]], months: list[date]) -> list[tuple[float, float, float]]:
    """(forecast, lower, upper) for each month, from level, annual growth and seasonality."""
    season = _season_index(history)
    deseason = [q / season[d.month] for d, q in history]
    last12, prev12 = deseason[-12:], deseason[-24:-12]
    level = sum(last12) / 12
    growth = (sum(last12) / sum(prev12) - 1) if len(prev12) == 12 and sum(prev12) else 0.0
    # In-sample error of the deseasonalised last year against its own level.
    resid = [(q - level) / level for q in last12] if level else [0.0]
    spread = (sum(r * r for r in resid) / len(resid)) ** 0.5
    out = []
    for k, month in enumerate(months, start=1):
        f = level * (1 + growth) ** ((k + 5.5) / 12) * season[month.month]
        out.append((round(f), round(f * (1 - Z80 * spread)), round(f * (1 + Z80 * spread))))
    return out


def forecast_demand(repo: Repository, product_ids: list[str], months: int = 6) -> DemandForecast:
    index = repo.index()
    snap = index.snapshot
    first_plan_month = date(index.as_of.year, index.as_of.month, 1)
    plan_months = horizon_months(first_plan_month, months)
    history: dict[str, list[tuple[date, float]]] = {}
    for h in snap.demand_history:
        if h.product_id in product_ids:
            history.setdefault(h.product_id, []).append((h.month, h.shipped_qty))
    for v in history.values():
        v.sort()

    method, model, notice = "seasonal_trend", "Seasonal trend baseline (local)", None
    results: dict[str, list[tuple[float, float, float]]] = {}
    remote = getattr(repo, "ai_forecast", None)
    if remote is not None:
        try:
            results = remote(product_ids, months, CONFIDENCE)
            method, model = "bigquery_timesfm", "BigQuery AI.FORECAST (TimesFM)"
        except Exception as exc:  # noqa: BLE001 - fall back to the local method
            log.warning("ai_forecast_failed", extra={"error": type(exc).__name__, "detail": str(exc)[:300]})
            notice = "BigQuery AI.FORECAST was unavailable, so the local seasonal-trend method was used."
            results = {}
    if not results:
        results = {pid: seasonal_trend(history[pid], plan_months) for pid in product_ids if pid in history}

    products = []
    for pid in product_ids:
        if pid not in results:
            continue
        plan = {d.forecast_month: d.forecast_qty for d in index.demand.get(pid, [])}
        points = [ForecastPoint(month=m.isoformat(), plan_qty=plan.get(m, 0.0), forecast_qty=float(f),
                                lower=float(lo), upper=float(hi))
                  for m, (f, lo, hi) in zip(plan_months, results[pid], strict=False)]
        plan_total = sum(p.plan_qty for p in points)
        fc_total = sum(p.forecast_qty for p in points)
        products.append(ProductForecast(
            product_id=pid, name=index.item_name(pid),
            history=[HistoryPoint(month=d.isoformat(), qty=q) for d, q in history.get(pid, [])],
            points=points, plan_total=plan_total, forecast_total=fc_total,
            delta_pct=round(fc_total / plan_total - 1, 4) if plan_total else 0.0))
    return DemandForecast(method=method, model=model, horizon_months=months, confidence_level=CONFIDENCE,
                          products=products, notice=notice)
