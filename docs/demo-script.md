# Demo Video Script (3:39)

Recorded from the live Cloud Run deployment at 1920×1080. Before recording:
select **Reset Demo** (sidebar), then open the Overview.

**Analyze Impact** starts the nine-agent workflow right away. It runs live in
about 15–30 seconds and is shown in real time, labelled "Live run · real time".
Other UI clips are played at up to 1.4× so they match the narration.

Narration: Google Cloud Text-to-Speech, voice `en-US-Chirp3-HD-Charon`, with
burned-in English captions (also in `RippleOps_demo_v2.srt`).

| Time | Screen | Action | Narration |
|---|---|---|---|
| 0:00–0:18 | Title → Overview | Title card (3 s), then the Overview. | "A supplier discontinues one chip. Which products use it? What does it cost us? Who needs to act? Today, that takes days of spreadsheets and meetings. RippleOps answers it in minutes." |
| 0:18–0:31 | New Change Event | **Analyze a Change → Use Demo Notice**. Gemini extracts the fields and matches the part. | "Here is a supplier's end-of-life notice. Gemini reads it, extracts the part, the change type, the last-time-buy date and the recommended replacement, and validates them against our product data." |
| 0:31–1:02 | Change Response | **Analyze Impact**; the nine agents stream in real time. End on the **Executive brief**. | "Now, nine Google ADK agents take the case. An impact analyst sizes the exposure. Then two teams work in parallel: a sourcing team scouts suppliers, while three due-diligence agents check performance, sanctions and supplier news. And a planning team forecasts demand and re-plans production. Every step streams live. A coordinator writes the executive brief." |
| 1:02–1:17 | Change Response | Highlight the Gemini and **Figures verified** badges on the agent cards. | "Each finding carries a Gemini badge and a figures-verified check. A grounding guardrail compares every number the agents write with the tool output, and replaces anything it cannot trace with calculated text." |
| 1:17–1:33 | Impact Analysis | Highlight the KPIs. Click **P300** to show both BOM paths. | "BigQuery Graph traces the chip through every bill of materials: twelve products in three families, four point two million dollars of revenue exposed, and only fifty-eight days of stock. Our Edge Controller Pro uses four of these chips, through two separate assembly paths." |
| 1:33–1:47 | Ask RippleOps | Type "Why is P300 high risk?". The answer cites 64 days of coverage and no approved alternative. | "Anyone can ask a follow-up question. Why is P300 high risk? The assistant answers by calling the same tools, so every number in its answer comes from the calculation, not from the model." |
| 1:47–2:09 | Sourcing | Crescent (76.8), Hanshan blocked, options table, supplier performance, news, compliance screening. | "Sourcing found five options. Crescent Semiconductor scores highest, as a long-term second source. A cheap clone is blocked by sanctions screening, and broker stock is flagged as bridge-only. Underneath sits the evidence: four quarters of delivery and quality data, supplier news, and a sanctions screen across every supplier." |
| 2:09–2:35 | Production Plan | Demand forecast, affected-product fill rate 64% → 100%, **What changes**, then **Approve Plan**. | "The demand planner forecasts with BigQuery's TimesFM model. The production planner re-plans thirteen weeks with OR-Tools, tests a bridge buy, and lifts fill rate on the affected products from sixty-four to one hundred percent. It lists exactly what changes on the shop floor: which products switch to the new chip, and which move to the flex line. The agent only proposes the plan. A planner approves it." |
| 2:35–2:49 | Scenario Simulator | Quick scenario **Replacement + copper + TW-US freight**. | "Want to test a decision first? Switching to the successor chip, with copper up twelve percent and freight up fifteen, pushes five products below our twenty percent margin target." |
| 2:49–3:06 | Actions | Highlight last-time buy, bridge buy, MCU-X200 validation, re-plan, pricing review. | "Finally, every department gets its next move. Procurement secures the last-time buy and the bridge stock. Engineering validates the new chip. Operations runs the approved plan, and finance reviews pricing. Every action cites the facts behind it." |
| 3:06–3:32 | Architecture | Animated diagram builds in step with the narration. | "Under the hood, it all runs on Google Cloud. The web app and the agent API run on Cloud Run. Gemini on Vertex AI powers nine ADK agents. BigQuery holds the product data, BigQuery Graph traces the bill of materials, AI.FORECAST predicts demand, and OR-Tools optimizes the plan. AI reasons; deterministic engines calculate." |
| 3:32–3:39 | End card | Live URL and repository. | "One change. Every impact. One decision." |

## Figures quoted

All figures come from the fictional seeded dataset and are asserted by tests.

| Figure | Source |
|---|---|
| 12 products, 3 families, $4.2M, 58 days | Impact analysis |
| P300: 4 units through two BOM paths; 64 days of coverage | Impact analysis, assistant |
| 5 sourcing options; Crescent 76.8 Preferred; Hanshan Blocked; Quantum Reclaim Bridge only | Sourcing |
| Affected-product fill rate 64% → 100% (agent-proposed plan with a 500-unit bridge buy) | Production Plan |
| 5 products below 20% with MCU-X200 + copper +12% + freight +15% | Scenario simulator |
| 13 weeks, 5 lines, 1,168 variables | OR-Tools solver output |
