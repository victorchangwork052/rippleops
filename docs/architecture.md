# Architecture

```text
Browser ── Next.js web (Cloud Run) ── /api/* proxy ──▶ FastAPI + ADK (Cloud Run)
                                                         │
                         ┌───────────────────────────────┼──────────────────────────┐
                         ▼                               ▼                          ▼
                  Gemini (Vertex AI)              Deterministic engines        BigQuery
                  notice extraction               bom · costing · impact       17 tables
                  ADK multi-agent workflow        scenario · risk · actions    bom_graph (GQL)
                  ADK assistant                   sourcing · scorecards        AI.FORECAST (TimesFM)
                  explanations / wording          OR-Tools CP-SAT planner
                                                         │
                                                  Mock third-party connectors
                                                  catalog · sanctions · news
```

## Backend (`apps/api/app`)

| Module | Responsibility |
|---|---|
| `seed/generator.py` | Deterministic, narrative-driven demo dataset (single source for local and BigQuery). |
| `db/repository.py` | `LocalRepository` (in-memory seed) and `get_repository()` backend switch. |
| `db/bigquery_repo.py` | Loads tables from BigQuery; traces the BOM with GQL (needs an Enterprise reservation), then recursive SQL, then in-memory. |
| `services/bom.py` | Path enumeration; effective qty = Σ over paths of Π edge qty. |
| `services/costing.py` | Cost roll-up: processing + purchase + raw material + freight + Σ qty × child. |
| `services/impact.py` | Current-state impact, coverage, alternative comparison, graph payload. |
| `services/scenario.py` | What-if engine with fixed-order driver attribution (replacement → material → freight). |
| `services/risk.py` | Deterministic Critical / High / Medium / Low rules with reasons. |
| `services/notice.py` | PDF/TXT/DOCX text extraction, Gemini structured extraction, rule fallback, validation. |
| `services/actions.py` | Rule-based action candidates; Gemini rewrites wording only if grounded. |
| `tools/registry.py` | Typed tools for the agent: `calculate_business_impact`, `trace_bom_impact`, `get_product_impact`, `run_scenario`, `get_action_plan`. |
| `agents/orchestrator.py` | Single ADK `LlmAgent` + tools; grounding check; deterministic fallback. |
| `ai/prompts.py` | All prompts, versioned. |
| `ai/grounding.py` | Flags numbers in AI text that are not traceable to tool output. |
| `seed/operations.py` | Production lines, routings, 13 weeks of work orders, 24 months of shipment history, supplier KPIs (own RNG, so core numbers never move). |
| `integrations/providers.py` | Interfaces + mock implementations for the distributor catalog, sanctions screening and supplier news. |
| `services/sourcing.py` | Merges approved vendors and catalog cross-references; weighted 0-100 scorecards with a compliance gate. |
| `services/forecast.py` | BigQuery `AI.FORECAST` (TimesFM) per product, or a local seasonal-trend method. |
| `services/planning.py` | Weekly material requirements; OR-Tools CP-SAT re-plan (lines × weeks × alternative part) vs. the current schedule. |
| `services/response.py` | `EventContext`: computes and caches every artifact once, for both pages and agents. |
| `agents/workflow.py` | ADK multi-agent tree (Sequential / Parallel / LlmAgent), streaming callbacks, grounding callback, deterministic fallback. |
| `agents/workflow_tools.py` | The agents' tools and deterministic findings. |
| `observability.py` | JSON logs with request ID, tool, duration, Gemini / BigQuery status, error category. |

### Cost model

Purchased components carry a purchase price (excluding index-linked raw
material), a raw-material surcharge (`material_weight_kg × price_per_kg`) and
inbound freight (`unit_weight_kg × lane rate`). Assemblies and finished goods add
their processing cost and roll up children by BOM quantity. Gross margin is
`(price − cost) / price`; changes are reported in percentage points.

### Inventory coverage

`coverage = available stock / (Σ effective qty × forecast over the horizon / horizon days)`.
Product-level coverage adds that product's finished-goods stock.

### Demo state

Events, analyses, scenarios and action plans live in process memory and are
cleared by **Reset Demo**; the API is deployed with one Cloud Run instance so
all requests share that state. Business data lives in BigQuery.

## Frontend (`apps/web`)

Next.js App Router with client pages that call the same-origin `/api/*` proxy
(`app/api/[...path]/route.ts`), which forwards to `API_BASE_URL` at request time.

| Route | Screen |
|---|---|
| `/` | Overview: exposure KPIs, active events, recent analysis |
| `/events`, `/events/new` | Event list; upload / demo notice / manual entry with Gemini extraction |
| `/analysis?event=` | Analysis workspace: dependency map (React Flow), KPIs, alternatives, product table, "Why?" panel |
| `/scenarios?event=` | Scenario Simulator with current-vs-scenario comparison and margin chart |
| `/actions?event=` | Recommended Response by department with status tracking |
| `/data` | Read-only browser for the demo tables |
| `/demo/mcu-x100` | One-step demo loader |
