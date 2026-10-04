"""The multi-agent change-response workflow (deterministic mode, no Gemini)."""

import json

from fastapi.testclient import TestClient

from app.agents.workflow import AGENTS, Recorder, agent_tree, build_agents
from app.main import app

client = TestClient(app)


def _new_event() -> str:
    client.post("/api/demo/reset")
    r = client.post("/api/events", json={"event_type": "COMPONENT_EOL", "part_id": "MCU-X100",
                                         "recommended_alternative_part_id": "MCU-X200", "source": "demo"})
    return r.json()["event_id"]


def test_agent_tree_shape():
    tree = agent_tree()
    assert tree.kind == "sequential"
    assert [c.name for c in tree.children] == ["impact_analyst", "response_research", "response_coordinator"]
    research = tree.children[1]
    assert research.kind == "parallel"
    assert [c.name for c in research.children] == ["sourcing_team", "planning_team"]


def test_adk_agents_build_without_calling_gemini():
    from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

    from app.agents.workflow_tools import WorkflowTools
    from app.api.deps import repo, settings, store
    from app.models.workflow import WorkflowRun
    from app.services.response import EventContext

    eid = _new_event()
    st = store()
    ctx = EventContext(repo(), st, settings(), st.get_event(eid))
    run = WorkflowRun(run_id="T", event_id=eid, mode="adk_gemini", model="m", status="RUNNING", started_at="",
                      tree=agent_tree(), steps=[], findings=[])
    root = build_agents(ctx, WorkflowTools(ctx), Recorder(run, None))
    assert isinstance(root, SequentialAgent)

    def walk(a):
        yield a
        for s in a.sub_agents:
            yield from walk(s)

    agents = list(walk(root))
    llm = [a for a in agents if isinstance(a, LlmAgent)]
    assert len(llm) == 9 and sum(isinstance(a, ParallelAgent) for a in agents) == 2
    assert {a.name for a in agents} == set(AGENTS)
    planner = next(a for a in llm if a.name == "production_planner")
    assert {t.__name__ for t in planner.tools} == {"optimize_production_plan", "get_bridge_supply_options",
                                                   "propose_production_plan"}


def test_workflow_streams_steps_and_proposes_a_plan():
    eid = _new_event()
    steps, done = [], None
    with client.stream("POST", "/api/workflow/run", json={"event_id": eid}) as r:
        event = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:])
                if event == "step":
                    steps.append(data)
                elif event == "done":
                    done = data
    assert done["status"] == "COMPLETED" and done["mode"] == "deterministic"
    started = {s["agent"] for s in steps if s["type"] == "agent_started"}
    assert started == set(AGENTS)
    tools = [s["tool"] for s in steps if s["type"] == "tool_call"]
    assert tools.count("optimize_production_plan") == 2  # without and with the bridge buy
    assert len(done["findings"]) == 9 and all(f["grounded"] for f in done["findings"])

    plan_id = done["proposed_plan_id"]
    planning = client.get(f"/api/planning/{eid}").json()
    assert planning["proposed_plan_id"] == plan_id
    proposed = next(p for p in planning["plans"] if p["plan_id"] == plan_id)
    assert proposed["status"] == "PROPOSED" and proposed["inputs"]["bridge_buy_qty"] == 500

    # Human-in-the-loop approval closes the matching action.
    decided = client.post(f"/api/planning/plans/{plan_id}/decision", json={"decision": "APPROVED"}).json()
    assert decided["status"] == "APPROVED"
    actions = client.get(f"/api/actions?event_id={eid}").json()["actions"]
    assert next(a for a in actions if a["rule"] == "approve_replan")["status"] == "DONE"
    assert {a["department"] for a in actions} >= {"Procurement", "Operations"}


def test_sourcing_endpoint():
    eid = _new_event()
    body = client.get(f"/api/sourcing/{eid}").json()
    assert len(body["sourcing"]["candidates"]) == 5
    assert body["assessment"]["blocked_candidate_ids"] == ["HMX-100@EXT-HANS"]


def test_non_component_events_are_rejected():
    client.post("/api/demo/reset")
    assert client.get("/api/sourcing/EVT-1002").status_code == 422
