# RippleOps — AI Change Impact Agent
## Development Handoff Specification for Codex / Claude Code

**Version:** 0.1  
**Date:** 2026-09-25  
**Target:** AI Builder Cup 2026 — Future of Work & Enterprise Productivity  
**Prototype submission deadline:** 2026-10-18  
**Product language:** **English only**  
**Primary goal:** Build a polished, reliable 3-minute demo prototype on Google Cloud.

---

# 0. Instructions to the Coding Agent

You are implementing a hackathon prototype named **RippleOps**.

Prioritize, in this order:

1. **A reliable end-to-end demo**
2. **Correct BOM and cost calculations**
3. **Clear visualization of business impact**
4. **Meaningful use of Gemini / Google AI**
5. **Polished enterprise UI/UX**
6. Additional integrations and advanced features

Do **not** over-engineer the prototype.

Do not build a full ERP, PLM, procurement, or supply-chain management system.

The main demonstration must work even if external systems are unavailable. Use a deterministic seeded demo dataset in BigQuery.

All user-facing text, field labels, buttons, charts, error messages, seeded business documents, AI responses, README content, and submission screenshots must be in **English**.

The application should feel like a modern enterprise intelligence product, **not a generic chatbot**.

---

# 1. Background / Problem Statement

Many manufacturing and technology companies manage products with complex, multi-level Bills of Materials (BOMs).

A single finished product may contain:

- Assemblies
- Sub-assemblies
- Components
- Raw-material exposure
- Supplier dependencies
- Shipping-lane dependencies

When a component is discontinued, becomes more expensive, or is affected by logistics or commodity-price changes, determining the full business impact is difficult.

Today, teams often need to manually coordinate across:

- Procurement
- Engineering
- Product Management
- Finance
- Sales
- Supply Chain

Typical questions include:

- Which finished products use this discontinued component?
- Is the component used directly or through multiple sub-assemblies?
- How many units of the component are required per finished product?
- Which products have the highest exposure?
- Is an approved alternative available?
- How much will the replacement increase product cost?
- Which products will fall below the target gross-margin threshold?
- How long will existing inventory last?
- What happens if copper prices rise at the same time?
- What happens if freight costs also increase?
- Which teams should take action first?

The challenge is not simply querying a BOM table.

The real challenge is understanding the **business ripple effect of a change**.

---

# 2. Product Concept

## Product name

**RippleOps**

## Positioning

**AI-powered enterprise change-impact intelligence**

## One-line pitch

> From supply change to business decision in minutes.

## Product promise

When an external or internal business change occurs, RippleOps should:

1. **Understand the change**
2. **Trace dependencies**
3. **Calculate financial impact**
4. **Simulate alternatives**
5. **Explain the impact**
6. **Recommend cross-functional actions**

Use this mental model throughout the product:

```text
CHANGE
  ↓
TRACE
  ↓
CALCULATE
  ↓
SIMULATE
  ↓
DECIDE
  ↓
ACT
```

---

# 3. Why This Fits "Future of Work"

Although the underlying data is supply-chain and BOM data, the product is positioned as an **enterprise decision and collaboration agent**, not a manufacturing-control system.

The core transformation is:

### Before

```text
Supplier notice
    ↓
Procurement searches part number
    ↓
Engineering checks BOM
    ↓
Finance recalculates cost
    ↓
Product team evaluates alternatives
    ↓
Sales identifies affected opportunities
    ↓
Teams meet and create action items
```

### With RippleOps

```text
Business change
    ↓
AI understands the event
    ↓
Dependency graph is automatically traced
    ↓
Cost / margin impact is calculated
    ↓
Scenarios are simulated
    ↓
AI explains the business risk
    ↓
Cross-functional action plan is generated
```

This directly supports enterprise:

- Knowledge accessibility
- Decision making
- Productivity
- Cross-functional collaboration
- Workflow execution

---

# 4. Hackathon Requirements to Preserve

The implementation must remain aligned with AI Builder Cup requirements.

Important constraints:

- The selected track is **Future of Work & Enterprise Productivity**.
- A **working prototype** is required.
- The solution must meaningfully use Google AI such as Gemini / Google Agent Platform.
- The prototype must be deployed on **Google Cloud**, such as Cloud Run or Firebase.
- Submission materials must be in **English**.
- The final demo video is limited to approximately **3 minutes**.
- Technical Merit & Gen AI Implementation is the largest judging category, so AI must contribute to the actual workflow rather than serve as a decorative chatbot.

---

# 5. Primary Demo Story

This scenario is the single most important use case.

Everything needed for this story must be completed before adding secondary features.

## Demo Event

A fictional supplier, **NovaChip Technologies**, sends an End-of-Life notice.

Example notice:

```text
PRODUCT DISCONTINUATION NOTICE

Supplier: NovaChip Technologies
Affected Part: MCU-X100
Last Time Buy Date: January 30, 2027
Last Ship Date: March 31, 2027
Recommended Replacement: MCU-X200

Reason:
The MCU-X100 product family will be discontinued as part of
the supplier's next-generation product transition.
```

The user uploads the notice.

RippleOps extracts:

```json
{
  "event_type": "COMPONENT_EOL",
  "supplier": "NovaChip Technologies",
  "part_id": "MCU-X100",
  "last_time_buy_date": "2027-01-30",
  "last_ship_date": "2027-03-31",
  "recommended_alternative": "MCU-X200"
}
```

The user clicks:

**Analyze Impact**

RippleOps then:

1. Identifies `MCU-X100`
2. Traverses the multi-level BOM
3. Finds all affected finished products
4. Calculates effective component quantity per product
5. Checks available inventory
6. Checks approved alternatives
7. Calculates revenue / cost / margin exposure
8. Displays a visual BOM impact graph

Initial result should show something similar to:

- **12 affected SKUs**
- **3 product families**
- **US$4.2M revenue exposure**
- **58 days inventory coverage**
- **4 products without an approved alternative**

The user then asks or selects:

> What if we replace MCU-X100 with MCU-X200?

RippleOps runs a deterministic scenario calculation.

Example:

- Alternative component cost: +18%
- Average finished-product unit cost: +US$4.73
- Average gross-margin impact: -1.9 percentage points
- 3 products fall below the target margin threshold

Then the user adds:

> Also assume copper increases by 12% and Taiwan-to-US freight increases by 15%.

RippleOps recalculates the scenario.

Finally, RippleOps generates a recommended action plan for:

- Procurement
- Engineering
- Finance
- Sales / Product Management

This complete flow is the target demo.

---

# 6. Core Product Principles

## 6.1 AI should reason, not perform financial arithmetic

Gemini should:

- Understand supplier notices
- Understand natural-language business questions
- Select the correct analytical tools
- Explain calculated results
- Compare scenarios
- Summarize risks
- Generate recommended actions

Gemini should **not** be the source of truth for:

- BOM quantities
- Component usage
- Cost calculations
- Margin calculations
- Inventory calculations
- Revenue calculations

All numeric business calculations must be performed deterministically by:

- BigQuery
- Python backend calculation functions
- Or another deterministic code path

The UI must consume structured numeric outputs.

Never extract business-critical numbers back out of free-form LLM prose.

---

## 6.2 Structured data first

Agent tools must return typed JSON objects.

Example:

```json
{
  "affected_products": 12,
  "revenue_exposure": 4200000,
  "inventory_coverage_days": 58,
  "products_below_margin_threshold": 3,
  "products": []
}
```

Gemini may explain this object, but the dashboard values must come from the structured result.

---

## 6.3 Explainability is part of the UX

Every major result should provide a "Why?" path.

Example:

> P300 has the highest margin impact because it requires four MCU-X100 units per finished product and currently operates close to the 20% target margin.

The user should be able to inspect:

```text
P300
 ↓
Assembly-A
 ↓ Qty 2
Subassembly-C
 ↓ Qty 2
MCU-X100

Effective MCU-X100 quantity = 4
```

---

# 7. MVP Scope

The following items are **required for the MVP**.

## P0 — Must Have

- English-only web interface
- Responsive desktop-first layout
- Seeded demo dataset
- Multi-level BOM data
- BigQuery storage
- BigQuery Graph BOM traversal
- Component End-of-Life event
- Supplier notice upload or built-in sample notice
- Gemini extraction of supplier notice
- Affected-product calculation
- Effective component quantity calculation
- Alternative-part comparison
- Product unit-cost calculation
- Gross-margin calculation
- What-if scenario engine
- BOM / impact graph visualization
- Impact summary cards
- AI explanation of results
- AI-generated cross-functional action plan
- Deployable to Google Cloud
- One-click "Reset Demo" function

## P1 — Strongly Preferred

- Raw-material price scenario
- Freight-cost scenario
- Compound scenarios
- Inventory coverage
- Product filtering / search
- Exportable impact summary
- Action owner / status UI
- Agent execution progress UI

## P2 — Stretch Only

Do these only after the core 3-minute demo is stable:

- Live commodity-price API
- Live freight API
- SAP integration
- Jira integration
- Email sending
- Slack / Google Chat integration
- Google Workspace integrations
- Multi-agent architecture
- Complex forecasting ML
- User authentication / RBAC
- Real production datasets
- Real-time ERP synchronization

---

# 8. Explicit Non-Goals

Do not build the following for the hackathon MVP:

- ERP replacement
- PLM replacement
- Full purchasing system
- Supplier portal
- Full order-management system
- Production scheduling
- Warehouse-management system
- Detailed accounting engine
- Full BI platform
- Full data-governance layer

The prototype exists to demonstrate **change-impact intelligence**.

---

# 9. Recommended Technical Architecture

## Frontend

Recommended:

- React
- Next.js using the current stable release
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide icons
- React Flow for BOM visualization
- Recharts for charts

Deployment options:

- Cloud Run, or
- Firebase hosting where appropriate

## Backend

Recommended:

- Python
- FastAPI
- Google Agent Development Kit (ADK)
- Google GenAI / Vertex AI Gemini
- BigQuery Python client

Deployment:

- Prefer Cloud Run for the first working version
- Agent Runtime may be used if setup is straightforward
- Do not block the project waiting for advanced Agent Platform setup

## Data

- BigQuery
- BigQuery Graph
- Google Cloud Storage for uploaded supplier documents if needed

## AI

- Gemini model through Google Cloud / supported Google AI APIs
- Google ADK for orchestration and tool calling

---

# 10. Target Architecture

```text
┌────────────────────────────────────────────┐
│               RippleOps Web                │
│ React / Next.js / TypeScript               │
│                                            │
│ Overview | Events | Analysis | Scenarios   │
│ Actions  | Data                            │
└────────────────────┬───────────────────────┘
                     │
                     │ HTTPS / JSON
                     ▼
┌────────────────────────────────────────────┐
│          FastAPI / ADK Application         │
│                                            │
│  RippleOps Orchestrator                    │
│          │                                 │
│          ├── Parse Notice Tool             │
│          ├── BOM Impact Tool               │
│          ├── Cost Scenario Tool            │
│          └── Action Plan Tool              │
└──────────┬─────────────────────┬───────────┘
           │                     │
           │                     │
           ▼                     ▼
┌────────────────────┐   ┌───────────────────┐
│ Gemini             │   │ BigQuery          │
│                    │   │                   │
│ Understanding      │   │ BigQuery Graph    │
│ Planning           │   │ SQL calculations  │
│ Explanation        │   │ Scenario data     │
│ Recommendations    │   │ Seeded demo data  │
└────────────────────┘   └───────────────────┘
```

---

# 11. Agent Architecture

Keep the MVP architecture simple.

Use **one orchestrator agent plus deterministic tools**.

Do not implement multiple autonomous agents until the complete demo works.

## RippleOps Orchestrator responsibilities

The orchestrator should:

1. Understand user intent
2. Select one or more tools
3. Pass structured parameters to tools
4. Receive structured results
5. Explain results
6. Recommend the next action

## Required tools

### `parse_change_notice`

Purpose:

Extract structured change-event information from supplier text or an uploaded document.

Input:

```json
{
  "document_text": "..."
}
```

Output:

```json
{
  "event_type": "COMPONENT_EOL",
  "supplier_name": "NovaChip Technologies",
  "part_id": "MCU-X100",
  "last_time_buy_date": "2027-01-30",
  "last_ship_date": "2027-03-31",
  "recommended_alternative_part_id": "MCU-X200",
  "confidence": 0.98
}
```

Gemini is appropriate for this step.

---

### `trace_bom_impact`

Purpose:

Find all affected products and paths for a component.

Input:

```json
{
  "part_id": "MCU-X100"
}
```

Output:

```json
{
  "component_id": "MCU-X100",
  "affected_product_count": 12,
  "paths": [],
  "products": [
    {
      "product_id": "P300",
      "effective_component_qty": 4,
      "paths_to_component": 2
    }
  ]
}
```

This tool should use BigQuery Graph or deterministic graph queries.

---

### `calculate_business_impact`

Purpose:

Calculate current exposure.

Input:

```json
{
  "part_id": "MCU-X100",
  "margin_threshold": 0.20
}
```

Output includes:

- Affected products
- Current unit cost
- Selling price
- Current margin
- Inventory coverage
- Revenue exposure
- Component usage

---

### `run_scenario`

Purpose:

Calculate a what-if scenario.

Example input:

```json
{
  "replacement_part_id": "MCU-X200",
  "commodity_adjustments": {
    "COPPER": 0.12
  },
  "freight_adjustments": {
    "TW-US-OCEAN": 0.15
  },
  "margin_threshold": 0.20
}
```

Output:

```json
{
  "summary": {
    "average_unit_cost_delta": 4.73,
    "average_margin_delta_points": -1.9,
    "products_below_margin_threshold": 5
  },
  "products": []
}
```

The scenario tool must be deterministic.

---

### `generate_action_plan`

Purpose:

Convert calculated impact into recommended cross-functional actions.

Input:

Structured impact / scenario result.

Output:

```json
{
  "actions": [
    {
      "department": "Procurement",
      "priority": "HIGH",
      "title": "Secure last-time-buy allocation",
      "reason": "Current inventory covers only 58 days.",
      "status": "PROPOSED"
    }
  ]
}
```

Gemini may generate the recommendation text, but it must be grounded in the supplied structured facts.

---

# 12. BigQuery Data Model

Keep the dataset understandable enough to explain in a 3-minute demo.

Recommended dataset:

- 50 finished goods
- 30 assemblies / sub-assemblies
- 150 components
- 8–12 suppliers
- 4–6 commodity types
- 5–8 shipping lanes
- 2–4 levels of BOM depth

All names should be fictional.

## `item_master`

Suggested fields:

```text
item_id STRING
item_name STRING
item_type STRING
product_family STRING
description STRING
base_processing_cost NUMERIC
unit_weight_kg NUMERIC
status STRING
```

`item_type`:

- FINISHED_GOOD
- ASSEMBLY
- COMPONENT

---

## `bom_edges`

```text
parent_item_id STRING
child_item_id STRING
qty_per_parent NUMERIC
uom STRING
effective_from DATE
effective_to DATE
```

This table creates the multi-level BOM graph.

---

## `suppliers`

```text
supplier_id STRING
supplier_name STRING
country STRING
risk_level STRING
```

---

## `supplier_parts`

```text
supplier_id STRING
part_id STRING
supplier_part_number STRING
current_unit_price NUMERIC
lead_time_days INT64
minimum_order_qty INT64
status STRING
shipping_lane_id STRING
```

---

## `alternate_parts`

```text
source_part_id STRING
alternative_part_id STRING
approval_status STRING
qualification_lead_time_days INT64
notes STRING
```

Approval values:

- APPROVED
- VALIDATION_REQUIRED
- NOT_APPROVED

---

## `inventory`

```text
item_id STRING
location_id STRING
on_hand_qty NUMERIC
allocated_qty NUMERIC
available_qty NUMERIC
snapshot_date DATE
```

---

## `product_demand`

```text
product_id STRING
forecast_month DATE
forecast_qty NUMERIC
open_order_qty NUMERIC
```

---

## `product_price`

```text
product_id STRING
market STRING
selling_price NUMERIC
currency STRING
effective_date DATE
```

---

## `material_exposure`

Use this for raw-material scenarios.

```text
item_id STRING
material_code STRING
material_weight_kg NUMERIC
```

Examples:

- COPPER
- ALUMINUM
- STEEL
- RESIN

---

## `material_price`

```text
material_code STRING
price_per_kg NUMERIC
currency STRING
effective_date DATE
```

---

## `shipping_lanes`

```text
shipping_lane_id STRING
origin STRING
destination STRING
mode STRING
freight_rate_per_kg NUMERIC
currency STRING
```

Example:

```text
TW-US-OCEAN
Taiwan
United States
Ocean
```

---

## `change_events`

```text
event_id STRING
event_type STRING
supplier_id STRING
affected_item_id STRING
event_date DATE
last_time_buy_date DATE
last_ship_date DATE
recommended_alternative_item_id STRING
source_document_uri STRING
status STRING
```

---

# 13. BigQuery Graph

Use BigQuery Graph primarily to demonstrate dependency traversal.

The important visual and technical story is:

```text
MCU-X100
 ↑
Assembly-A
 ↑
Product-P100
```

and:

```text
MCU-X100
 ↑
Subassembly-C
 ↑
Assembly-A
 ↑
Product-P300
```

The application needs to return:

- Every affected finished product
- Every relevant path
- Effective component quantity for each finished product

## Effective component quantity

For each path from finished product to component:

```text
path quantity =
qty(edge 1)
× qty(edge 2)
× ...
× qty(edge n)
```

If a finished product reaches the same component through multiple BOM paths:

```text
effective component quantity =
SUM(path quantity for all valid paths)
```

Example:

```text
P300
 ↓ Qty 2
Assembly-A
 ↓ Qty 2
MCU-X100
```

Effective usage:

```text
2 × 2 = 4 MCU-X100 per P300
```

Never let the LLM infer this value.

---

# 14. Cost Model

The cost engine must be simple, explainable, and deterministic.

Do not attempt to reproduce a full enterprise costing model.

Recommended model:

```text
Item Cost =
Base Processing Cost
+ Raw Material Cost
+ Child Item Cost
+ Allocated Freight Cost
```

For a component:

```text
Raw Material Cost =
SUM(material_weight_kg × material_price_per_kg)
```

Freight:

```text
Freight Cost =
unit_weight_kg × freight_rate_per_kg
```

Finished-product cost should recursively roll up child costs using BOM quantities.

---

## Gross margin

```text
Gross Margin =
(Selling Price - Product Cost) / Selling Price
```

Display gross margin as a percentage.

Also calculate change in **percentage points**.

Example:

```text
Current margin = 24.1%
Scenario margin = 20.3%

Margin change = -3.8 percentage points
```

Do not label this as a "-3.8%" change.

---

# 15. Scenario Engine

The scenario engine is the second major feature after BOM impact tracing.

## Scenario A — Component Replacement

```text
MCU-X100 → MCU-X200
```

Effects may include:

- Different purchase price
- Different material composition
- Different shipping lane
- Different lead time

---

## Scenario B — Raw Material Change

Example:

```text
Copper +12%
```

Only items with copper exposure should change.

---

## Scenario C — Freight Change

Example:

```text
TW-US Ocean Freight +15%
```

Only affected supplier / shipping-lane relationships should change.

---

## Scenario D — Compound Scenario

Example:

```text
Replacement: MCU-X200
Copper: +12%
TW-US Ocean Freight: +15%
```

The value of RippleOps is highest when multiple changes can be simulated together.

---

# 16. Seeded Demo Dataset Requirements

The demo data must intentionally create interesting results.

Do not generate completely random values.

The dataset should be designed around the demo narrative.

## Required anchor component

```text
Part ID: MCU-X100
Supplier: NovaChip Technologies
Status: EOL announced
```

## Required replacement

```text
Part ID: MCU-X200
Approval: APPROVED or VALIDATION_REQUIRED
Purchase cost: approximately 18% higher than MCU-X100
```

## Required affected finished products

At least:

```text
P100
P200
P300
P410
P500
```

Total affected products should ideally be approximately 12.

Create varying effective component quantities:

```text
P100 → 1
P200 → 2
P300 → 4
P410 → 1
P500 → 3
```

P300 should be intentionally designed to have a significant cost / margin impact.

At least:

- 3 products should fall below 20% margin after component replacement
- 5 products should fall below 20% margin in the compound scenario

These are demo targets, not arbitrary outcomes.

Seed values accordingly.

---

# 17. API Design

Suggested API routes:

## Change event

```text
POST /api/events/parse
POST /api/events
GET  /api/events
GET  /api/events/{event_id}
```

## Analysis

```text
POST /api/impact/analyze
GET  /api/impact/{event_id}
```

## Scenarios

```text
POST /api/scenarios/run
GET  /api/scenarios/{scenario_id}
```

## Actions

```text
POST /api/actions/generate
GET  /api/actions
PATCH /api/actions/{action_id}
```

## Demo

```text
POST /api/demo/reset
GET  /api/demo/sample-notice
```

Keep request / response models typed.

Prefer Pydantic models in the Python backend.

---

# 18. Frontend Information Architecture

Primary navigation:

```text
RippleOps

Overview
Events
Impact Analysis
Scenarios
Actions
Data
```

Do not add more top-level navigation items during the MVP.

---

# 19. Main UI Screens

## 19.1 Overview

Purpose:

Immediately communicate what RippleOps does and show active business changes.

### Layout

Top:

```text
Good morning.

Understand how business changes ripple across
products, cost, margin, and teams.
```

Primary CTA:

**Analyze a Change**

Secondary CTA:

**Load Demo Scenario**

Below:

### Active Change Events

Cards:

- Component EOL
- Supplier Price Increase
- Material Price Change
- Freight Change

### Exposure Summary

Example cards:

- Products at Risk
- Revenue Exposure
- Margin at Risk
- Open Actions

### Recent Analysis

Show the latest event and status.

---

## 19.2 New Change Event

Use a focused modal or dedicated page.

Options:

```text
Upload Supplier Notice
Enter Change Manually
Use Demo Notice
```

Upload area:

```text
Drop a supplier notice here

PDF, TXT, or DOCX
```

After parsing, show editable extracted fields:

```text
Event type
Supplier
Affected part
Last time buy
Last ship date
Recommended replacement
```

CTA:

**Analyze Impact**

---

## 19.3 Analysis Workspace

This is the most important screen.

Desktop layout:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Event header                                                        │
│ MCU-X100 End-of-Life     High Risk      NovaChip Technologies       │
├────────────────┬────────────────────────────────┬───────────────────┤
│ Event Details  │                                │ Business Impact   │
│                │       BOM IMPACT GRAPH         │                   │
│ Supplier       │                                │ 12 SKUs           │
│ Dates          │                                │ $4.2M Revenue     │
│ Alternative    │                                │ 58 Days Coverage  │
│                │                                │ 4 No Alternative  │
├────────────────┴────────────────────────────────┴───────────────────┤
│ Affected Products                                                   │
│ Product | Usage | Cost | Margin | Exposure | Risk                  │
└─────────────────────────────────────────────────────────────────────┘
```

The graph must be the visual focal point.

---

## 19.4 Scenario Simulator

Header:

**Scenario Simulator**

Subtext:

> Model multiple changes before committing to a decision.

Controls:

### Component

```text
Replace MCU-X100 with
[ MCU-X200 ▼ ]
```

### Commodity

```text
Copper
[ +12% ]
```

### Freight

```text
Taiwan → United States / Ocean
[ +15% ]
```

### Threshold

```text
Target gross margin
[ 20% ]
```

CTA:

**Run Scenario**

Results:

```text
Current                    Scenario
-------------------------------------------
Average unit cost          +$4.73
Average gross margin       -1.9 pts
Products below threshold   5
Revenue at risk            $...
```

Include product-level table and chart.

---

## 19.5 Action Plan

Header:

**Recommended Response**

Group cards by department:

### Procurement

- Secure a six-month last-time-buy allocation
- Confirm supplier allocation deadline
- Negotiate replacement pricing

### Engineering

- Validate MCU-X200 for P300 and P410
- Prioritize products with low inventory coverage

### Finance

- Review pricing for products below the 20% target margin

### Sales / Product

- Review open quotes for high-risk products
- Flag pricing commitments that extend past inventory coverage

Each action has:

- Department
- Priority
- Reason
- Owner
- Status

Statuses:

```text
Proposed
Accepted
In Progress
Done
```

For MVP, actions may remain local / database records.

No external task platform is required.

---

# 20. AI Interaction UX

Do not make the entire application a chat window.

The AI should feel embedded in the workflow.

Recommended pattern:

- Main structured application
- Bottom-right assistant trigger or top command bar
- Context-aware suggested questions

Examples:

```text
Ask RippleOps...

"What products are most exposed?"
"Why is P300 at high risk?"
"What happens if copper rises 10%?"
"Which actions should we prioritize?"
```

The assistant should understand which event / scenario the user is currently viewing.

---

# 21. Agent Progress UX

When analysis runs, show meaningful progress.

Example:

```text
Analyzing change...

✓ Identified component MCU-X100
✓ Traced multi-level BOM
✓ Checked inventory
✓ Evaluated approved alternatives
✓ Calculated cost and margin impact
● Preparing recommendations
```

Do not show fake technical jargon.

If progress is simulated for demo smoothness, the actual final result must still come from the real backend.

---

# 22. UI / UX Design Direction

## Design personality

The product should feel:

- Modern
- Intelligent
- Enterprise-ready
- Calm
- Precise
- Data-driven
- Premium but not decorative

Avoid:

- Cyberpunk styling
- Excessive gradients
- Neon AI visuals
- Robot illustrations
- Generic chat bubbles everywhere
- Heavy glassmorphism
- Dense ERP-style forms
- Huge empty hero sections inside the app

Think:

> modern enterprise intelligence workspace

---

# 23. Visual Design System

## Theme

Use a bright neutral enterprise interface as the default.

Recommended:

- White / off-white page background
- Neutral gray surfaces
- Deep slate text
- Blue / indigo primary accent
- Amber for warning
- Red for critical impact
- Green for positive / safe states

Dark mode is optional and should not delay the MVP.

---

## Typography

Recommended font:

**Inter**

Reasons:

- Excellent UI legibility
- Modern enterprise appearance
- Open source
- Commercial use permitted under SIL Open Font License 1.1

Use tabular numbers for financial KPIs where possible.

Suggested hierarchy:

```text
Page title       28–32px / semibold
Section title    18–20px / semibold
Card metric      28–36px / semibold
Body             14–16px
Caption          12–13px
```

Avoid ultra-light font weights.

---

# 24. Icon System — Important

## Primary icon library

Use **Lucide** / `lucide-react`.

Lucide is the preferred icon set.

Requirements:

- Outline / line icons only
- Default size: 18–20px in controls
- 20–24px in navigation
- Use consistent stroke width
- Do not mix unrelated icon styles
- Avoid filled icons unless required for a very specific status indicator

Lucide is open source and released under the **ISC License**, which permits commercial use.

## Approved fallback

**Heroicons Outline**

Heroicons is MIT licensed and suitable for commercial projects.

Do not use both Lucide and Heroicons in the same UI unless an icon is genuinely unavailable.

## Suggested icon mapping

```text
Overview             LayoutDashboard
Events               Radio / BellRing
Impact Analysis      Network
Scenarios            SlidersHorizontal
Actions              ListChecks
Data                 Database

Supplier             Factory
Component            Cpu
Product              Box
Assembly             Boxes
BOM                   GitBranch / Network
Price                 CircleDollarSign
Margin                Percent
Inventory             Warehouse
Freight               Ship
Raw Material          PackageOpen
Warning               TriangleAlert
Critical              CircleAlert
Approved              CircleCheck
Calendar              CalendarDays
Upload                UploadCloud
Search                Search
Ask AI                Sparkles
Run analysis          Play
Scenario              FlaskConical
Reset Demo            RotateCcw
Download              Download
Filter                SlidersHorizontal
More                  Ellipsis
```

Do not use emoji as application icons.

---

# 25. Approved Open-Source Frontend Libraries

Use libraries with permissive licenses suitable for commercial usage.

Recommended stack:

| Library | Purpose | License |
|---|---|---|
| Lucide | Line icons | ISC |
| Heroicons | Optional icon fallback | MIT |
| Tailwind CSS | Styling | MIT |
| shadcn/ui | UI components | MIT |
| React Flow / XYFlow | BOM graph | MIT |
| Recharts | Charts | MIT |
| Inter | Typeface | SIL OFL 1.1 |

Keep the relevant license files / notices in the repository.

Do not copy icons or illustrations from random websites.

Do not use paid icon packs, unlicensed SVG assets, or proprietary brand artwork unless explicitly approved.

---

# 26. BOM Graph UX

Use `@xyflow/react` / React Flow.

The graph should communicate dependency and impact, not behave like a generic node editor.

## Node types

### Component

Icon:

`Cpu`

Fields:

```text
MCU-X100
Component
EOL
```

### Assembly

Icon:

`Boxes`

### Finished Product

Icon:

`Box`

Show:

```text
P300
Edge Controller Pro
High Impact
```

---

## Visual hierarchy

The affected component should be easy to identify.

Affected paths should stand out from unrelated nodes.

Suggested interaction:

- Click node → open side panel
- Hover edge → show `Qty per parent`
- Select finished product → highlight its complete path to affected component
- Fit graph automatically on first render
- Provide zoom controls
- Provide "Reset View"

Do not make graph nodes draggable by default if dragging has no business meaning.

---

# 27. KPI Card UX

Examples:

```text
Affected SKUs
12
Across 3 product families
```

```text
Revenue Exposure
$4.2M
Next 6 months
```

```text
Inventory Coverage
58 days
Based on current forecast
```

```text
Products Below Margin Target
5
Target: 20%
```

Every metric must state enough context to avoid misleading the user.

---

# 28. Risk Language

Use consistent risk levels:

```text
Critical
High
Medium
Low
```

Risk should be derived from deterministic rules for the demo.

Example rule set:

### Critical

- No approved alternative AND inventory coverage < 45 days

or

- Scenario margin < 10%

### High

- Inventory coverage < 90 days

or

- Scenario margin below target

### Medium

- Approved alternative exists but has material cost impact

### Low

- Sufficient coverage and approved alternative available

Do not ask Gemini to invent risk scores.

---

# 29. Accessibility

Minimum requirements:

- Keyboard-accessible controls
- Visible focus states
- WCAG-friendly contrast
- Do not communicate risk with color alone
- Icon-only buttons require accessible labels
- Tables should have proper headings
- Loading indicators should include text
- Charts require text equivalents / tooltips

---

# 30. Responsive Design

Primary target:

```text
1440 × 900 desktop
```

Also support:

- 1280px laptop
- Basic tablet layout

Mobile is not the primary hackathon experience.

Do not spend excessive time building perfect mobile graph interactions.

---

# 31. Empty / Loading / Error States

These are required.

## Empty state

Example:

```text
No change events yet

Upload a supplier notice or load the demo scenario
to see how RippleOps maps business impact.
```

Buttons:

```text
Analyze a Change
Load Demo Scenario
```

## Error

Example:

```text
We couldn't identify a valid part number in this notice.

Review the extracted information or enter the part manually.
```

Never show raw stack traces to the user.

---

# 32. English UI Copy Rules

Everything visible in the product must be English.

Good:

```text
Analyze Impact
Run Scenario
Affected Products
Revenue Exposure
Inventory Coverage
Recommended Response
Why this matters
```

Avoid vague AI phrases such as:

```text
AI Insights
AI Magic
Smart Result
Amazing Recommendation
```

Prefer concrete business language.

---

# 33. Development Order

The coding agent must follow this order unless a blocking issue requires adjustment.

---

## Phase 1 — Project Skeleton

Goal:

Get the application running locally immediately.

Tasks:

- Create monorepo or simple frontend/backend structure
- Configure TypeScript frontend
- Configure Python backend
- Add environment-variable template
- Add lint / formatting
- Add basic CI if quick
- Build global layout
- Add primary navigation
- Add design tokens
- Install approved open-source dependencies

Deliverable:

```text
Frontend runs
Backend runs
Health endpoint works
Navigation works
```

---

## Phase 2 — Seed Data

Goal:

Make the core story deterministic.

Tasks:

- Create BigQuery dataset
- Create tables
- Write seed generator
- Seed fictional product hierarchy
- Ensure MCU-X100 affects approximately 12 finished goods
- Seed alternative MCU-X200
- Seed costs, inventory, forecasts, materials, freight
- Add reset / reseed script

Deliverable:

A repeatable dataset that produces the intended demo outcomes.

---

## Phase 3 — BOM Traversal

Goal:

Complete the most important technical feature.

Tasks:

- Create BigQuery Graph definition
- Implement traversal
- Return all affected finished products
- Return paths
- Calculate effective quantity
- Validate multi-path and multi-level cases
- Add automated tests

Deliverable:

```text
trace_bom_impact("MCU-X100")
```

returns stable structured results.

Do not proceed to AI polish until this works.

---

## Phase 4 — Cost Engine

Goal:

Calculate business impact deterministically.

Tasks:

- Roll up component costs
- Calculate finished-product cost
- Calculate selling price / margin
- Add inventory coverage
- Calculate exposure metrics
- Validate all formulas with unit tests

Deliverable:

Current-state impact summary.

---

## Phase 5 — Scenario Engine

Goal:

Support decision simulation.

Implement in this order:

1. Component replacement
2. Raw-material adjustment
3. Freight adjustment
4. Compound scenario

Deliverable:

A scenario result that shows current vs scenario values.

---

## Phase 6 — Core UI

Goal:

Turn working backend functions into a compelling visual product.

Implement:

1. Overview
2. Event details
3. Impact Analysis
4. BOM graph
5. Product impact table
6. Scenario Simulator
7. Action Plan

Do not add chat yet.

---

## Phase 7 — Gemini Notice Understanding

Goal:

Make GenAI part of the real workflow.

Tasks:

- Load sample supplier notice
- Send document text / supported content to Gemini
- Enforce structured response schema
- Validate extracted part against BigQuery
- Allow user to correct fields
- Create change event

Deliverable:

Supplier notice → structured event → real analysis.

---

## Phase 8 — ADK Orchestration

Goal:

Use Gemini as an enterprise analytical agent.

Tasks:

- Add RippleOps orchestrator
- Register deterministic tools
- Implement context-aware natural-language queries
- Require tool use for calculations
- Ground explanations in tool outputs
- Add basic guardrails against invented business values

Deliverable:

User can ask:

```text
Why is P300 high risk?
```

or:

```text
What happens if copper increases by 12%?
```

and receive grounded answers.

---

## Phase 9 — Action Recommendations

Goal:

Complete the Future of Work story.

Tasks:

- Generate cross-functional response
- Ground every action in calculated facts
- Show actions by department
- Allow Accept / In Progress / Done
- Persist state minimally

Deliverable:

Impact → Decision → Action.

---

## Phase 10 — Demo Polish

Tasks:

- Add agent progress states
- Add animations sparingly
- Improve graph layout
- Improve loading states
- Add "Load Demo Scenario"
- Add "Reset Demo"
- Add seeded supplier notice
- Test on fresh browser
- Deploy to Google Cloud
- Verify public prototype URL
- Record demo

---

# 34. Suggested Repository Structure

```text
rippleops/
│
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── events/
│   │   │   ├── impact/
│   │   │   ├── scenarios/
│   │   │   ├── actions/
│   │   │   └── assistant/
│   │   └── lib/
│   │
│   └── api/
│       ├── app/
│       │   ├── agents/
│       │   ├── api/
│       │   ├── models/
│       │   ├── services/
│       │   ├── tools/
│       │   └── db/
│       └── tests/
│
├── data/
│   ├── seed/
│   ├── sql/
│   └── demo-documents/
│
├── scripts/
│   ├── seed_bigquery.py
│   └── reset_demo.py
│
├── docs/
│   ├── architecture.md
│   ├── demo-script.md
│   └── licenses.md
│
├── .env.example
├── README.md
└── LICENSES/
```

A simpler structure is acceptable if it improves development speed.

---

# 35. Environment Variables

Example:

```text
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_LOCATION=
BIGQUERY_DATASET=
GEMINI_MODEL=
GOOGLE_APPLICATION_CREDENTIALS=
GCS_BUCKET=
APP_ENV=
```

Never commit credentials.

---

# 36. Testing Priorities

## Unit tests

Required for:

- Effective BOM quantity
- Cost rollup
- Gross margin
- Component replacement
- Material-price adjustment
- Freight adjustment
- Compound scenario

## Integration tests

At minimum:

```text
MCU-X100 → affected products
MCU-X100 → replacement MCU-X200
MCU-X100 + copper +12%
MCU-X100 + copper +12% + freight +15%
```

## UI smoke test

The complete demo should be testable from a clean browser session.

---

# 37. Definition of Done — MVP

The prototype is considered demo-ready only when all of the following pass.

## Start

- Public deployment opens successfully
- UI is English
- No login is required for judge demo, unless authentication is already reliable
- "Load Demo Scenario" works

## Event

- Sample supplier notice loads
- Gemini identifies MCU-X100
- Extracted data appears in structured fields
- User can click "Analyze Impact"

## Impact

- BOM graph renders
- 12-ish affected products appear
- Product paths are inspectable
- KPIs populate from deterministic calculation
- Product table shows cost / margin / usage

## Scenario

- User can select MCU-X200
- Scenario calculation completes
- Current vs scenario values render
- Copper +12% works
- Freight +15% works
- Compound scenario works

## AI

- User can ask "Why is P300 high risk?"
- Gemini provides an explanation grounded in structured results
- Gemini does not invent unsupported numbers

## Action

- Recommended actions render by department
- Actions clearly reference actual scenario facts

## Reliability

- Reset Demo returns application to initial state
- No broken navigation
- No obvious console errors
- No raw backend errors in UI
- Complete demo can be repeated multiple times

---

# 38. Three-Minute Demo Flow

This should guide development decisions.

If a feature does not improve this flow, it is not a priority.

## 0:00–0:20 — Problem

Narration:

> Modern products contain thousands of interconnected parts.  
> When one supplier changes a component, understanding the impact across products, cost, margin, and teams can take days.

Show RippleOps Overview.

---

## 0:20–0:45 — Change

Load supplier EOL notice.

Gemini extracts:

```text
MCU-X100
End of Life
Last time buy: Jan 30, 2027
Replacement: MCU-X200
```

Click:

**Analyze Impact**

---

## 0:45–1:20 — Trace

Show progress:

```text
Identified component
Traced multi-level BOM
Checked inventory
Calculated exposure
```

Reveal graph.

Show:

```text
12 affected SKUs
3 product families
$4.2M revenue exposure
58 days inventory coverage
```

This is Wow Moment #1.

---

## 1:20–1:50 — Calculate

Open P300.

Show dependency path and effective quantity.

Example:

```text
P300 uses 4 units of MCU-X100.
```

Explain why it is highly exposed.

---

## 1:50–2:15 — Simulate

Select:

```text
Replace MCU-X100 → MCU-X200
```

Run scenario.

Show cost and margin changes.

---

## 2:15–2:35 — Compound Scenario

Add:

```text
Copper +12%
TW-US freight +15%
```

Run again.

Show:

```text
5 products fall below 20% gross margin.
```

This is Wow Moment #2.

---

## 2:35–2:55 — Decide / Act

Show recommended response:

```text
Procurement
Engineering
Finance
Sales
```

Highlight 3–4 actions.

---

## 2:55–3:00 — Ending

Display:

```text
One change.
Every impact.
One decision.
```

RippleOps logo / product name.

---

# 39. Product Copy Examples

Use these as preferred copy.

## Home

**Headline**

> Understand the ripple effect before it becomes a business problem.

**Subheadline**

> Trace product dependencies, quantify financial impact, simulate scenarios, and coordinate the next action with AI.

---

## Analysis

> Business Impact

> Dependency Map

> Affected Products

> Inventory Coverage

> Revenue Exposure

> Margin Impact

> Approved Alternatives

---

## Scenario

> Scenario Simulator

> Model multiple changes before committing to a decision.

> Run Scenario

> Compare to Current State

---

## Explanation

> Why this product is at risk

> P300 uses four MCU-X100 units through two BOM levels and currently operates close to the 20% target gross margin.

---

## Actions

> Recommended Response

> Turn analysis into a coordinated cross-functional plan.

---

# 40. Naming Conventions

Use human-readable fictional names.

Do not use real customer names.

Examples:

Suppliers:

```text
NovaChip Technologies
Pacific Components
Orion Materials
Atlas Electronics
```

Product families:

```text
Edge Control
Industrial Gateway
Vision System
Smart I/O
```

Finished products:

```text
P100 Edge Controller
P200 Industrial Gateway
P300 Edge Controller Pro
P410 Vision Hub
P500 Smart I/O Gateway
```

---

# 41. Security / Demo Hygiene

Even though this is a prototype:

- No credentials in repository
- No customer data
- No real supplier confidential documents
- No customer trademarks without permission
- Use fictional datasets
- Use least-privilege Google Cloud service accounts where practical
- Validate file upload type and size
- Sanitize file names
- Do not allow arbitrary server-side file execution

---

# 42. Observability

Minimum logging:

- Request ID
- Tool invoked
- Execution time
- BigQuery query status
- Gemini call status
- Scenario ID
- Error category

Do not log:

- API keys
- Authentication tokens
- Secret credentials

A basic Cloud Logging setup is sufficient.

---

# 43. Performance Targets

Prototype targets:

```text
Initial app load           < 3 seconds on normal broadband
Impact analysis            ideally < 8 seconds
Scenario calculation       ideally < 5 seconds
Graph interaction          visually immediate
```

If Gemini processing is slow, keep the UI responsive with meaningful progress indicators.

Do not fake final analytical results.

---

# 44. Failure / Fallback Strategy

The demo must remain recoverable.

## If document parsing fails

Allow:

**Use Extracted Demo Data**

or manual editing.

## If Gemini explanation fails

The deterministic analysis should still render.

## If BigQuery Graph setup becomes blocked

Temporary fallback:

- Recursive SQL / backend graph traversal for functionality

But keep BigQuery Graph as the intended technical implementation before final submission if possible.

## If Agent Runtime causes deployment delay

Deploy ADK / FastAPI on Cloud Run.

Do not let infrastructure complexity block the demo.

---

# 45. Development Rules for Codex / Claude Code

1. Implement one vertical slice at a time.
2. Keep functions small and typed.
3. Do not add dependencies without a clear reason.
4. Prefer deterministic logic for business calculations.
5. Keep AI prompts centralized and versioned.
6. Put all UI strings in English.
7. Do not hard-code calculated KPI values in frontend components.
8. Seed demo values in the database / seed script.
9. Every analytical number shown in the UI must have a traceable source.
10. Write tests before modifying cost formulas.
11. Do not implement P2 features while P0 items are unstable.
12. Do not redesign navigation without a strong reason.
13. Use Lucide line icons consistently.
14. Keep third-party license notices in the repository.
15. Optimize for a repeatable hackathon demo.

---

# 46. Suggested First Coding Milestone

The first milestone should **not use Gemini yet**.

Build this first:

```text
Seed BigQuery
    ↓
MCU-X100
    ↓
Trace BOM
    ↓
Return affected products
    ↓
Calculate component quantities
    ↓
Render graph
    ↓
Render impact table
```

Acceptance test:

Opening:

```text
/demo/mcu-x100
```

or loading the demo scenario should show:

- A graph
- Affected products
- Effective quantities
- Current cost
- Current margin

Only after this works should Gemini be added.

This prevents AI integration from hiding data-model or cost-engine bugs.

---

# 47. Suggested Second Coding Milestone

Add deterministic scenario simulation.

Required flow:

```text
MCU-X100
    ↓
Replace with MCU-X200
    ↓
Recalculate product cost
    ↓
Recalculate margin
    ↓
Show current vs scenario
```

Then add:

```text
Copper +12%
```

Then:

```text
Freight +15%
```

Then compound them.

---

# 48. Suggested Third Coding Milestone

Add Gemini.

Required:

```text
Supplier notice
    ↓
Gemini structured extraction
    ↓
Validated part ID
    ↓
Deterministic analysis tools
    ↓
Gemini explanation
```

This is the desired relationship between AI and business logic.

---

# 49. Suggested Final Polish Milestone

Focus only on things visible in the 3-minute video:

- Smooth event extraction
- Good loading feedback
- Beautiful BOM graph
- Strong KPI cards
- Clear current-vs-scenario comparison
- One excellent explanation
- One excellent action plan
- Consistent icons
- No broken states
- Fast reset

Do not spend the final days adding invisible infrastructure.

---

# 50. Open-Source / Commercial-Use License Notes

The preferred UI stack was intentionally selected around permissively licensed open-source tools.

## Lucide

- License: ISC
- Suitable for personal and commercial use
- Preferred icon library

## Heroicons

- License: MIT
- Suitable fallback outline icon library

## shadcn/ui

- License: MIT

## Tailwind CSS

- License: MIT

## React Flow / XYFlow

- License: MIT
- Commercial projects are allowed under the open-source license

## Recharts

- License: MIT

## Inter

- License: SIL Open Font License 1.1
- Commercial use permitted subject to the license terms

Include required copyright / license notices in the repository.

Before final commercial production use, review the exact license text for all dependency versions included in the build.

---

# 51. Relevant Google Platform Notes

Validated for this project direction as of 2026-09-25:

## BigQuery Graph

BigQuery Graph became generally available on September 1, 2026.

It allows graph relationships and GQL-based traversal to operate natively with BigQuery data, which is well suited to multi-level BOM dependency analysis and supply-chain "blast radius" use cases.

## Google Agent Development Kit

ADK is Google's open-source framework for building AI agents and supports:

- Tools
- Workflow orchestration
- Multi-agent architectures
- Deployment to Google Cloud environments

For the MVP, use one orchestrator plus deterministic tools.

## Cloud Deployment

AI Builder Cup requires a working Google Cloud-hosted prototype. Prefer:

- Cloud Run
- Firebase where useful
- Agent Runtime if it does not add schedule risk

---

# 52. Reference Links

Google Cloud — BigQuery Graph:
https://cloud.google.com/blog/products/data-analytics/bigquery-graph-connecting-data-and-ai-at-scale/

Google Cloud — Agent Development Kit:
https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/adk

Google Cloud — Agent Runtime / ADK:
https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

AI Builder Cup — Themes and Requirements:
https://aibuildercup.com/themes.html

AI Builder Cup — Timeline:
https://aibuildercup.com/

Lucide:
https://lucide.dev/

Heroicons:
https://github.com/tailwindlabs/heroicons

shadcn/ui:
https://github.com/shadcn-ui/ui

React Flow:
https://github.com/xyflow/xyflow

Recharts:
https://github.com/recharts/recharts

Inter:
https://github.com/rsms/inter

---

# 53. Final Product Definition

**RippleOps** is an AI-powered enterprise change-impact agent that helps cross-functional teams understand how supplier disruptions, component changes, raw-material prices, and logistics costs ripple through complex product structures.

By combining **Gemini**, **Google Agent Development Kit**, **BigQuery**, and **BigQuery Graph**, RippleOps:

- Understands business-change notices
- Traces multi-level BOM dependencies
- Quantifies product and financial impact
- Simulates alternative scenarios
- Explains why specific products are at risk
- Converts analysis into coordinated business actions

The product should demonstrate one clear idea exceptionally well:

> **A single business change can affect hundreds of relationships. RippleOps turns that ripple effect into a decision people can act on.**

---

# 54. Final Priority Reminder

When choosing between:

```text
More features
```

and

```text
A flawless 3-minute story
```

choose the flawless 3-minute story.

The minimum winning-quality sequence is:

```text
Supplier Notice
      ↓
Gemini Understands
      ↓
BigQuery Graph Traces
      ↓
Cost Engine Calculates
      ↓
Scenario Simulator Compares
      ↓
Gemini Explains
      ↓
Teams Act
```

Everything else is secondary.
