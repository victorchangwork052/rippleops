import pytest
from fastapi.testclient import TestClient

from app.agents import orchestrator
from app.ai.grounding import collect_numbers, unverified_numbers
from app.main import app

POOL = collect_numbers({"revenue": 4200147.0, "margin": 0.218, "delta": -1.89, "days": 58, "cost": 4.725,
                        "text": "Inventory covers 64 days"})


@pytest.mark.parametrize("text", [
    "Revenue exposure is $4.2M.", "Revenue exposure is $4,200,147.", "Margin is 21.8%.",
    "Margin falls by 1.9 pts.", "Coverage is 58 days.", "Covers 64 days.", "Cost rises by $4.73.",
    "P300 uses MCU-X100 via ASM-A200 (EVT-2001) by January 30, 2027.",
])
def test_grounded_numbers_pass(text):
    assert unverified_numbers(text, POOL) == []


@pytest.mark.parametrize("text,bad", [
    ("Revenue exposure is $5.1M.", "$5.1M"), ("Margin is 23.4%.", "23.4%"), ("Coverage is 71 days.", "71"),
])
def test_invented_numbers_are_flagged(text, bad):
    assert unverified_numbers(text, POOL) == [bad]


@pytest.fixture()
def client_event():
    c = TestClient(app)
    c.post("/api/demo/reset")
    return c, c.post("/api/demo/load").json()["event"]["event_id"]


def test_why_is_p300_high_risk_is_grounded(client_event):
    c, event_id = client_event
    r = c.post("/api/assistant/ask", json={"event_id": event_id, "question": "Why is P300 high risk?"}).json()
    assert r["method"] == "deterministic"
    assert "P300" in r["answer"] and "4 MCU-X100 units" in r["answer"]
    assert {t["name"] for t in r["tool_calls"]} >= {"get_product_impact", "trace_bom_impact"}
    assert r["grounding"]["verified"], r["grounding"]


def test_copper_what_if_runs_scenario_tool(client_event):
    c, event_id = client_event
    r = c.post("/api/assistant/ask", json={"event_id": event_id,
                                           "question": "What happens if copper increases by 12%?"}).json()
    assert r["tool_calls"][0]["name"] == "run_scenario"
    assert r["tool_calls"][0]["args"] == {"material_code": "COPPER", "material_change": 0.12}
    assert r["scenario_id"] and c.get(f"/api/scenarios/{r['scenario_id']}").status_code == 200
    assert r["grounding"]["verified"], r["grounding"]


def test_explain_product_is_grounded(client_event):
    c, event_id = client_event
    r = c.post(f"/api/impact/{event_id}/explain", json={"product_id": "p300"}).json()
    assert "P300" in r["text"] and r["grounding"]["verified"]


def test_agent_answer_with_invented_number_is_flagged(client_event, monkeypatch):
    c, event_id = client_event

    async def fake_agent(session, question, session_id, context):
        session.calls.append({"name": "get_product_impact", "args": {"product_id": "P300"}})
        session.outputs.append({"gross_margin": 0.218})
        return "P300 runs at 21.8% margin and will lose $9.99M."

    monkeypatch.setattr(orchestrator, "_run_agent", fake_agent)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: type("S", (), {
        "gemini_configured": True, "gemini_model": "test-model"})())
    r = c.post("/api/assistant/ask", json={"event_id": event_id, "question": "How bad is P300?"}).json()
    assert r["method"] == "adk_gemini"
    assert r["grounding"] == {"verified": False, "unverified_values": ["$9.99M"]}


def test_agent_failure_falls_back(client_event, monkeypatch):
    c, event_id = client_event

    async def broken_agent(*_):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(orchestrator, "_run_agent", broken_agent)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: type("S", (), {
        "gemini_configured": True, "gemini_model": "test-model"})())
    r = c.post("/api/assistant/ask", json={"event_id": event_id, "question": "Why is P300 high risk?"}).json()
    assert r["method"] == "deterministic" and "unavailable" in r["notice"]
