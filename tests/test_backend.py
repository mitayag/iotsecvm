from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["actions_enabled"] is False


def test_lab_listing_has_eighteen_weeks() -> None:
    response = client.get("/api/labs")
    assert response.status_code == 200
    labs = response.json()["labs"]
    assert len(labs) == 18
    week01 = next(lab for lab in labs if lab["id"] == "week01")
    assert week01["compose_present"] is True
    assert week01["status"] == "implemented"


def test_lab_detail_and_missing_lab() -> None:
    response = client.get("/api/labs/week01")
    assert response.status_code == 200
    assert response.json()["safety"]["external_ports"] == []
    assert client.get("/api/labs/week99").status_code == 404
    assert client.get("/api/labs/not-a-lab").status_code == 404


def test_actions_are_disabled_by_default() -> None:
    response = client.post("/api/labs/week01/actions/start")
    assert response.status_code == 403
