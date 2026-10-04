"""Third-party data providers used by the sourcing agents.

Each provider is a small interface. The demo ships mock implementations that
read fictional fixtures, so results are deterministic and no external account
is needed. In production the same interfaces are backed by real services:

* PartsCatalog      -> distributor cross-reference APIs (e.g. DigiKey, Mouser)
* SanctionsScreener -> sanctions / export-control screening (e.g. OpenSanctions)
* SupplierNews      -> news monitoring or web search
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

FIXTURES = Path(__file__).parent / "fixtures"
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "POSITIVE": 3}


@dataclass(frozen=True)
class CrossReference:
    mpn: str
    manufacturer: str
    match_type: str  # DIRECT_SUCCESSOR | FUNCTIONAL_EQUIVALENT | PIN_TO_PIN_CLONE
    pin_compatible: bool
    lifecycle: str
    notes: str


@dataclass(frozen=True)
class Offer:
    mpn: str
    distributor: str
    supplier_id: str
    channel: str  # AUTHORIZED | BROKER | FACTORY_DIRECT
    country: str
    unit_price: float
    stock: int
    lead_time_days: int
    date_code: str
    notes: str


@dataclass(frozen=True)
class Company:
    supplier_id: str
    name: str
    country: str


@dataclass(frozen=True)
class SanctionsMatch:
    entity_id: str
    listed_name: str
    list_name: str
    program: str
    listed_on: str
    matched_on: str


@dataclass(frozen=True)
class NewsArticle:
    supplier: str
    date: str
    category: str
    severity: str  # HIGH | MEDIUM | LOW | POSITIVE
    source: str
    headline: str
    summary: str


class PartsCatalog(Protocol):
    provider: str

    def cross_references(self, mpn: str) -> list[CrossReference]: ...

    def offers(self, mpn: str) -> list[Offer]: ...

    def manufacturer(self, name: str) -> Company | None: ...


class SanctionsScreener(Protocol):
    provider: str
    list_name: str

    def screen(self, name: str) -> list[SanctionsMatch]: ...


class SupplierNews(Protocol):
    provider: str

    def search(self, supplier_name: str) -> list[NewsArticle]: ...


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _norm(name: str) -> str:
    name = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    stop = {"co", "ltd", "inc", "corp", "corporation", "company", "limited", "llc"}
    return " ".join(t for t in name.split() if t not in stop)


class MockPartsCatalog:
    mock = True

    def __init__(self) -> None:
        data = _load("distributor_catalog.json")
        self.provider = data["provider"]
        self._xref = data["cross_references"]
        self._offers = data["offers"]
        self._makers = data["manufacturers"]
        self._dists = data["distributors"]

    def cross_references(self, mpn: str) -> list[CrossReference]:
        return [CrossReference(**x) for x in self._xref.get(mpn, [])]

    def offers(self, mpn: str) -> list[Offer]:
        out = []
        for o in self._offers.get(mpn, []):
            d = self._dists[o["distributor"]]
            out.append(Offer(mpn=mpn, distributor=o["distributor"], supplier_id=d["supplier_id"],
                             channel=d["channel"], country=d["country"], unit_price=o["unit_price"],
                             stock=o["stock"], lead_time_days=o["lead_time_days"], date_code=o["date_code"],
                             notes=o["notes"]))
        return out

    def manufacturer(self, name: str) -> Company | None:
        m = self._makers.get(name)
        return Company(m["supplier_id"], name, m["country"]) if m else None

    def distributor(self, name: str) -> Company | None:
        d = self._dists.get(name)
        return Company(d["supplier_id"], name, d["country"]) if d else None


class MockSanctionsScreener:
    mock = True

    def __init__(self) -> None:
        data = _load("sanctions_list.json")
        self.provider = data["provider"]
        self.list_name = data["list_name"]
        self._entities = data["entities"]

    def screen(self, name: str) -> list[SanctionsMatch]:
        wanted = _norm(name)
        hits = []
        for e in self._entities:
            for candidate in [e["name"], *e["aliases"]]:
                if _norm(candidate) == wanted:
                    hits.append(SanctionsMatch(e["entity_id"], e["name"], self.list_name, e["program"],
                                               e["listed_on"], candidate))
                    break
        return hits


class MockSupplierNews:
    mock = True

    def __init__(self) -> None:
        data = _load("supplier_news.json")
        self.provider = data["provider"]
        self._articles = [NewsArticle(**a) for a in data["articles"]]

    def search(self, supplier_name: str) -> list[NewsArticle]:
        wanted = _norm(supplier_name)
        hits = [a for a in self._articles if _norm(a.supplier) == wanted]
        return sorted(hits, key=lambda a: (SEVERITY_ORDER[a.severity], a.date))


@dataclass(frozen=True)
class Integrations:
    catalog: MockPartsCatalog
    sanctions: MockSanctionsScreener
    news: MockSupplierNews


@lru_cache
def get_integrations() -> Integrations:
    return Integrations(MockPartsCatalog(), MockSanctionsScreener(), MockSupplierNews())
