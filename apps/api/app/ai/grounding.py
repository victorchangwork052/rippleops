"""Guardrail against invented business values.

Every number in an AI answer must be traceable to a structured tool output or
the event context (allowing for display formatting: percent, $K/$M, rounding).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# A number not glued to letters/hyphens (so P300, MCU-X100, EVT-2001 are ignored).
_NUM = re.compile(
    r"(?<![A-Za-z0-9_\-])(?P<neg>[-−])?\$?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?"
    r"\s?(?P<suffix>[KkMm](?![A-Za-z])|%|\s?pts?\b|\s?percentage points\b)?")
_NUM_IN_TEXT = re.compile(r"-?\d+(?:\.\d+)?")
ALWAYS_OK = {0.0, 1.0, 2.0, 3.0, 100.0}
_MONTH_BEFORE = re.compile(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+$", re.IGNORECASE)


def collect_numbers(obj: Any, out: set[float] | None = None) -> set[float]:
    out = set() if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM_IN_TEXT.findall(obj.replace(",", "")):
            out.add(float(m))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_numbers(v, out)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            collect_numbers(v, out)
    elif hasattr(obj, "model_dump"):
        collect_numbers(obj.model_dump(), out)
    return out


def _candidates(pool: Iterable[float]) -> list[float]:
    cands = []
    for p in pool:
        for v in (p, p * 100.0):
            cands.append(abs(v))
    return cands


def unverified_numbers(text: str, pool: set[float]) -> list[str]:
    """Return the raw number strings in `text` that no source value supports."""
    cands = _candidates(pool)
    bad: list[str] = []
    for m in _NUM.finditer(text):
        raw = m.group(0).strip()
        if _MONTH_BEFORE.search(text[max(0, m.start() - 12):m.start()]):
            continue  # day of month in a written date
        digits = m.group("num").replace(",", "")
        dec = m.group("dec") or ""
        value = float(f"{digits}.{dec}" if dec else digits)
        suffix = (m.group("suffix") or "").strip().lower()
        scale = 1_000_000.0 if suffix == "m" else 1_000.0 if suffix == "k" else 1.0
        target = value * scale
        # Half a unit in the last shown decimal place, at the shown scale.
        tol = 0.5 * (10 ** -len(dec)) * scale + 1e-9
        if target in ALWAYS_OK or 2000 <= target <= 2100 and not dec:  # small counts, calendar years
            continue
        if not any(abs(c - target) <= tol for c in cands):
            bad.append(raw)
    return bad
