import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.actions import ActionRewrite, PlanRewrite
from app.services import actions as actions_service

COMPOUND = {"replacement_part_id": "MCU-X200", "commodity_adjustments": {"COPPER": 0.12},
            "freight_adjustments": {"TW-US-OCEAN": 0.15}}


@pytest.fixture()
def ctx():
    c = TestClient(app)
    c.post("/api/demo/reset")
    event_id = c.post("/api/demo/load").json()["event"]["event_id"]
    scenario = c.post("/api/scenarios/run", json={"event_id": event_id, **COMPOUND}).json()
    return c, event_id, scenario


def test_plan_covers_every_department_with_grounded_facts(ctx):
    c, event_id, scenario = ctx
    plan = c.post("/api/actions/generate", json={"event_id": event_id, "scenario_id": scenario["scenario_id"]}).json()
    assert plan["method"] == "deterministic"
    assert {a["department"] for a in plan["actions"]} == {"Procurement", "Engineering", "Finance", "Sales / Product"}
    assert plan["grounding"]["verified"], plan["grounding"]
    by_rule = {a["rule"]: a for a in plan["actions"]}
    assert "58 days" in by_rule["ltb_allocation"]["reason"]
    assert set(by_rule["validate_alternative"]["related_products"]) == {"P300", "P410", "P420", "P500"}
    finance = by_rule["review_pricing"]
    assert "5 products fall below target" in finance["reason"]
    assert set(finance["related_products"]) == {"P300", "P500", "P200", "P120", "P410"}
    for a in plan["actions"]:
        assert a["status"] == "PROPOSED" and a["owner"] and a["facts"]


def test_plan_defaults_to_latest_scenario(ctx):
    c, event_id, scenario = ctx
    plan = c.post("/api/actions/generate", json={"event_id": event_id}).json()
    assert plan["scenario_id"] == scenario["scenario_id"]


def test_action_status_updates(ctx):
    c, event_id, _ = ctx
    plan = c.post("/api/actions/generate", json={"event_id": event_id}).json()
    aid = plan["actions"][0]["action_id"]
    for status in ("ACCEPTED", "IN_PROGRESS", "DONE"):
        r = c.patch(f"/api/actions/{aid}", json={"status": status})
        assert r.status_code == 200 and r.json()["status"] == status
    assert c.get("/api/actions/summary").json()["open"] == len(plan["actions"]) - 1
    assert c.patch(f"/api/actions/{aid}", json={"status": "SHIPPED"}).status_code == 422
    assert c.patch("/api/actions/NOPE", json={"status": "DONE"}).status_code == 404


def test_ungrounded_gemini_rewrite_is_rejected(ctx, monkeypatch):
    c, event_id, _ = ctx
    first_id = f"{event_id}-A01"

    def fake_generate(system, contents, schema, **_):
        return PlanRewrite(summary="Invented summary with $9.9M at risk.", actions=[
            ActionRewrite(id=first_id, title="Buy 99,999 extra units now", reason="Because 12 is a nice number.")])

    monkeypatch.setattr(actions_service, "generate_structured", fake_generate)
    monkeypatch.setattr(actions_service, "get_settings", lambda: type("S", (), {
        "gemini_configured": True, "gemini_model": "test-model"})())
    plan = c.post("/api/actions/generate", json={"event_id": event_id}).json()
    assert plan["method"] == "deterministic"
    assert "$9.9M" not in plan["summary"]
    assert "99,999" not in plan["actions"][0]["title"]


def test_grounded_gemini_rewrite_is_accepted(ctx, monkeypatch):
    c, event_id, _ = ctx
    first_id = f"{event_id}-A01"

    def fake_generate(system, contents, schema, **_):
        return PlanRewrite(summary="MCU-X100 affects 12 products.", actions=[
            ActionRewrite(id=first_id, title="Lock in last-time-buy volume", reason="Stock covers only 58 days.")])

    monkeypatch.setattr(actions_service, "generate_structured", fake_generate)
    monkeypatch.setattr(actions_service, "get_settings", lambda: type("S", (), {
        "gemini_configured": True, "gemini_model": "test-model"})())
    plan = c.post("/api/actions/generate", json={"event_id": event_id}).json()
    assert plan["method"] == "gemini"
    assert plan["actions"][0]["title"] == "Lock in last-time-buy volume"
    assert plan["summary"] == "MCU-X100 affects 12 products."
