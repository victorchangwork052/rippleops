# RippleOps — AI Change Impact Agent

> From supply change to business decision in minutes.

RippleOps is an enterprise change-impact agent. When a supplier discontinues a
component, or raw-material and freight costs move, it traces the change through
multi-level Bills of Materials, calculates cost / margin / revenue / inventory
exposure, simulates alternatives, explains the risk, and turns it into a
cross-functional action plan.

```text
CHANGE → TRACE → CALCULATE → SOURCE → RE-PLAN → DECIDE → ACT
```

A team of nine Google ADK agents runs the response: an impact analyst, a
sourcing team (scout, three parallel due-diligence agents, evaluator), a
planning team (demand planner, production planner) and a response
coordinator. The production plan is only proposed; a person approves it.

Built for the AI Builder Cup 2026 (Future of Work & Enterprise Productivity).
All data is fictional.

## How AI and business logic divide the work

| Gemini (via Google ADK) | Deterministic engine (BigQuery / Python) |
|---|---|
| Reads supplier notices into structured events | BOM traversal and effective quantities (BigQuery Graph) |
| Agents decide which tools to call and in what order | Cost roll-up, gross margin, scenarios |
| Production planner decides whether a bridge buy is worth testing, compares plans and proposes one | Production re-plan with Google OR-Tools CP-SAT |
| Explains forecasts, scorecards and plans | Demand forecast with BigQuery `AI.FORECAST` (TimesFM) |
| Writes findings, the executive brief and action wording | Supplier scorecards, compliance gate, risk levels, actions |

### Multi-agent workflow (`apps/api/app/agents/workflow.py`)

```text
change_response_workflow            SequentialAgent
├─ impact_analyst                   LlmAgent   analyze_change_impact
├─ response_research                ParallelAgent
│   ├─ sourcing_team                SequentialAgent
│   │   ├─ sourcing_scout           LlmAgent   find_sourcing_options
│   │   ├─ supplier_due_diligence   ParallelAgent
│   │   │   ├─ performance_auditor  LlmAgent   get_supplier_performance
│   │   │   ├─ compliance_screener  LlmAgent   screen_suppliers
│   │   │   └─ risk_news_monitor    LlmAgent   search_supplier_news
│   │   └─ supplier_evaluator       LlmAgent   score_suppliers
│   └─ planning_team                SequentialAgent
│       ├─ demand_planner           LlmAgent   forecast_demand, calculate_material_requirements
│       └─ production_planner       LlmAgent   optimize_production_plan, get_bridge_supply_options,
│                                              propose_production_plan
└─ response_coordinator             LlmAgent   generate_action_plan
```

* Agents share findings through ADK session state (`output_key` and `{key?}`
  instruction templating).
* ADK callbacks stream every agent and tool step to the UI as server-sent
  events (`POST /api/workflow/run`).
* An `after_model_callback` checks every number an agent writes against the tool
  outputs and replaces ungrounded text with a deterministic finding.
* Without Gemini, the same tools run in the same order with deterministic findings.

External data (distributor cross-references, sanctions screening, supplier news)
comes from mock connectors with fictional fixtures
(`apps/api/app/integrations/`). Each is an interface that a production API
(e.g. DigiKey / Mouser, OpenSanctions, a news API) can implement.

Every number in the UI comes from structured tool output. AI text is checked by
a grounding guardrail (`apps/api/app/ai/grounding.py`): any figure that cannot be
traced to a calculated value is flagged, and ungrounded explanations or action
wording fall back to deterministic text.

## Quick start (local, no Google Cloud required)

Prerequisites: Python 3.11+, Node.js 24+.

```bash
# API
cd apps/api
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# Web (second terminal)
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000 and select **Load Demo Scenario**, or go straight
to http://localhost:3000/demo/mcu-x100.

Without Gemini credentials the app runs fully, and labels AI-generated text as
"Calculated summary". To enable Gemini locally, copy `.env.example` to
`apps/api/.env` and set either `GEMINI_API_KEY`, or `GOOGLE_CLOUD_PROJECT` with
Application Default Credentials (`gcloud auth application-default login`).

## Demo story (seeded, deterministic)

NovaChip Technologies announces End-of-Life for **MCU-X100**
(last time buy Jan 30, 2027; replacement MCU-X200). The seeded dataset produces:

| Result | Value |
|---|---|
| Affected SKUs | 12 across 3 product families |
| Revenue exposure (next 6 months) | $4.2M |
| MCU-X100 inventory coverage | 58 days |
| Products without an approved alternative | 4 |
| MCU-X200 replacement | +18% part price, +$4.73 avg unit cost, −1.9 pts avg margin, 3 products below 20% |
| + Copper +12%, TW→US ocean freight +15% | 5 products below 20% |

These are asserted by `apps/api/tests/test_demo_story.py`. See
[docs/demo-script.md](docs/demo-script.md) for the 3-minute walkthrough.

## Google Cloud

```bash
# 1. Seed BigQuery (tables + BigQuery Graph) and verify the graph trace
apps/api/.venv/Scripts/python scripts/seed_bigquery.py --project MY_PROJECT

# 2. Deploy API + web to Cloud Run
PROJECT=MY_PROJECT REGION=us-central1 scripts/deploy_cloud_run.sh

# Reset a deployment before a demo
python scripts/reset_demo.py --api https://rippleops-api-....run.app
```

The API runs with `DATA_BACKEND=bigquery`: tables are read from BigQuery and the
BOM is traced with a GQL query over the `bom_graph` property graph
(`apps/api/app/db/sql/`), falling back to recursive SQL if the graph query fails.

BigQuery Graph queries require an Enterprise (or Enterprise Plus) edition
reservation. The demo project uses an autoscaling reservation with a baseline of
0 slots, so it only bills while queries run:

```bash
bq mk --project_id=MY_PROJECT --location=US --reservation --edition=ENTERPRISE   --slots=0 --autoscale_max_slots=50 rippleops-graph
bq mk --project_id=MY_PROJECT --location=US --reservation_assignment   --reservation_id=MY_PROJECT:US.rippleops-graph --job_type=QUERY   --assignee_type=PROJECT --assignee_id=MY_PROJECT
```

## Tests

```bash
cd apps/api && .venv/Scripts/python -m pytest -q     # unit + integration + API
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```

## Repository layout

```text
apps/api     FastAPI + Google ADK orchestrator, deterministic engines, tests
apps/web     Next.js (App Router), Tailwind, React Flow, Recharts, Lucide
data/seed    CSV export of the deterministic demo dataset
scripts      seed_bigquery.py, reset_demo.py, deploy_cloud_run.sh
docs         architecture, demo script, third-party licenses
LICENSES     License texts of bundled open-source UI libraries
```

See [docs/architecture.md](docs/architecture.md) for details.
