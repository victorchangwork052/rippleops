import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    c = TestClient(app)
    c.post("/api/demo/reset")
    return c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers["x-request-id"]


def test_demo_flow_end_to_end(client):
    loaded = client.post("/api/demo/load").json()
    event_id = loaded["event"]["event_id"]
    assert loaded["event"]["status"] == "ANALYZED"

    impact = client.get(f"/api/impact/{event_id}").json()
    assert impact["summary"]["affected_product_count"] == 12

    rep = client.post("/api/scenarios/run", json={"event_id": event_id, "replacement_part_id": "MCU-X200"}).json()
    assert rep["summary"]["products_below_margin_threshold"] == 3

    compound = client.post("/api/scenarios/run", json={
        "event_id": event_id, "replacement_part_id": "MCU-X200",
        "commodity_adjustments": {"COPPER": 0.12}, "freight_adjustments": {"TW-US-OCEAN": 0.15}}).json()
    assert compound["summary"]["products_below_margin_threshold"] == 5
    assert client.get(f"/api/scenarios/{compound['scenario_id']}").status_code == 200


def test_reset_clears_user_state(client):
    event_id = client.post("/api/demo/load").json()["event"]["event_id"]
    client.post("/api/demo/reset")
    assert client.get(f"/api/events/{event_id}").status_code == 404
    events = client.get("/api/events").json()
    assert {e["source"] for e in events} == {"seed"}


def test_create_event_rejects_unknown_part_with_friendly_message(client):
    r = client.post("/api/events", json={"part_id": "MCU-Z999"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert "couldn't find part" in body["message"]
    assert "Traceback" not in r.text


def test_create_event_normalizes_part_id(client):
    r = client.post("/api/events", json={"part_id": " mcu-x100 ", "recommended_alternative_part_id": "mcu-x200"})
    assert r.status_code == 201
    assert r.json()["affected_item_id"] == "MCU-X100"
    assert r.json()["supplier_name"] == "NovaChip Technologies"


def test_non_component_event_is_not_analyzable(client):
    r = client.post("/api/impact/analyze", json={"event_id": "EVT-1002"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "not_analyzable"


def test_invalid_scenario_input(client):
    event_id = client.post("/api/demo/load").json()["event"]["event_id"]
    r = client.post("/api/scenarios/run", json={"event_id": event_id, "freight_adjustments": {"XX": 0.1}})
    assert r.status_code == 422
    assert "Unknown shipping lane" in r.json()["error"]["message"]


def test_data_browser(client):
    summary = client.get("/api/data/summary").json()
    counts = {t["name"]: t["rows"] for t in summary["tables"]}
    assert counts["item_master"] == 230
    page = client.get("/api/data/tables/item_master", params={"q": "MCU-X1", "limit": 5}).json()
    assert page["total"] >= 2
    assert client.get("/api/data/tables/secrets").status_code == 404
