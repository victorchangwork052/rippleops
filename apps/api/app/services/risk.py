"""Deterministic risk rules (handoff section 28). Gemini never assigns risk."""

from __future__ import annotations

from dataclasses import dataclass

CRITICAL_COVERAGE_DAYS = 45
HIGH_COVERAGE_DAYS = 90
CRITICAL_MARGIN = 0.10
MATERIAL_COST_IMPACT = 0.01  # 1% of unit cost

RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass(frozen=True)
class RiskInput:
    has_approved_alternative: bool
    coverage_days: float
    margin: float
    margin_threshold: float
    replacement_cost_increase_pct: float | None  # fraction of current unit cost


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def assess(r: RiskInput) -> tuple[str, list[str]]:
    """Return (risk level, reasons). Reasons quote only the inputs."""
    reasons: list[str] = []
    cov = f"{int(r.coverage_days)} days"

    if not r.has_approved_alternative and r.coverage_days < CRITICAL_COVERAGE_DAYS:
        reasons.append(f"No approved alternative and inventory covers only {cov} (under {CRITICAL_COVERAGE_DAYS}).")
    if r.margin < CRITICAL_MARGIN:
        reasons.append(f"Gross margin {_pct(r.margin)} is below the {_pct(CRITICAL_MARGIN)} critical floor.")
    if reasons:
        return "CRITICAL", reasons

    if r.coverage_days < HIGH_COVERAGE_DAYS:
        reasons.append(f"Inventory covers {cov}, under the {HIGH_COVERAGE_DAYS}-day planning window.")
    if r.margin < r.margin_threshold:
        reasons.append(f"Gross margin {_pct(r.margin)} is below the {_pct(r.margin_threshold)} target.")
    if not r.has_approved_alternative:
        reasons.append("No approved alternative for this product; validation is required.")
    if r.coverage_days < HIGH_COVERAGE_DAYS or r.margin < r.margin_threshold:
        return "HIGH", reasons

    if not r.has_approved_alternative:
        return "MEDIUM", reasons
    if r.replacement_cost_increase_pct is not None and r.replacement_cost_increase_pct >= MATERIAL_COST_IMPACT:
        reasons.append(f"Approved alternative raises unit cost by {_pct(r.replacement_cost_increase_pct)}.")
        return "MEDIUM", reasons
    reasons.append(f"Inventory covers {cov} and an approved alternative is available.")
    return "LOW", reasons
