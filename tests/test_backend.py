from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_helper
from backend.app.main import app
from backend.app.settings import SETTINGS, get_settings
from backend.helper.client import HelperError

client = TestClient(app)


class FakeHelper:
    def __init__(self, error: Exception | None = None):
        self.calls: list[tuple[str, str | None, dict]] = []
        self.error = error

    def call(self, action: str, *, lab: str | None = None, **fields) -> dict:
        self.calls.append((action, lab, fields))
        if self.error:
            raise self.error
        if action == "status":
            return {
                "ok": True,
                "action": action,
                "lab": lab,
                "result": {
                    "stdout": (
                        '[{"Name":"iotlab_w01_camera","Service":"camera",'
                        '"State":"running","Health":"healthy","Publishers":[]}]'
                    ),
                    "stderr": "",
                    "duration_ms": 5,
                },
            }
        return {
            "ok": True,
            "action": action,
            "lab": lab,
            "result": {"stdout": "done", "stderr": "", "duration_ms": 12},
        }


@pytest.fixture
def enabled_client():
    fake = FakeHelper()
    settings = replace(
        SETTINGS, enable_actions=True, helper_socket=Path("/tmp/fake-helper.sock")
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_helper] = lambda: fake
    try:
        yield TestClient(app), fake
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["actions_enabled"] is False
    assert payload["helper"]["helper_available"] is False


def test_lab_listing_has_eighteen_weeks_and_categories() -> None:
    response = client.get("/api/labs")
    assert response.status_code == 200
    labs = response.json()["labs"]
    assert len(labs) == 18
    week01 = next(lab for lab in labs if lab["id"] == "week01")
    assert week01["compose_present"] is True
    assert week01["status"] == "implemented"
    assert week01["availability"] == "available"
    assert week01["module_type"] == "lab"

    week02 = next(lab for lab in labs if lab["id"] == "week02")
    assert week02["availability"] == "planned"

    week18 = next(lab for lab in labs if lab["id"] == "week18")
    assert week18["module_type"] == "assessment"
    assert week18["availability"] == "planned"


def test_lab_detail_inventory_and_missing_lab() -> None:
    response = client.get("/api/labs/week01")
    assert response.status_code == 200
    payload = response.json()
    assert payload["safety"]["external_ports"] == []
    assert {device["name"] for device in payload["device_inventory"]} == {
        "camera",
        "gateway",
        "controller",
    }
    assert {service["port"] for service in payload["expected_services"]} == {
        22,
        1883,
        8080,
        8554,
    }
    assert client.get("/api/labs/week99").status_code == 404
    assert client.get("/api/labs/not-a-lab").status_code == 404


def test_instructions_endpoint() -> None:
    response = client.get("/api/labs/week01/instructions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "markdown"
    assert "Week 01" in payload["content"]
    planned = client.get("/api/labs/week02/instructions")
    assert planned.status_code == 200
    assert planned.json()["source"] in ("README.md", "lab.yaml")


def test_actions_are_disabled_by_default() -> None:
    response = client.post("/api/labs/week01/actions/start")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "actions_disabled"


def test_status_requires_helper() -> None:
    response = client.get("/api/labs/week01/status")
    assert response.status_code == 503


def test_enabled_manager_runs_start_stop_and_reset(enabled_client) -> None:
    manager, fake = enabled_client
    for action in ("start", "stop", "reset"):
        response = manager.post(f"/api/labs/week01/actions/{action}")
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "ok"
    assert [call[0] for call in fake.calls] == ["start", "stop", "reset"]
    assert all(call[1] == "week01" for call in fake.calls)


def test_enabled_manager_rejects_planned_and_unknown_actions(enabled_client) -> None:
    manager, fake = enabled_client
    assert manager.post("/api/labs/week02/actions/start").status_code == 409
    assert manager.post("/api/labs/week01/actions/explode").status_code == 404
    assert fake.calls == []


def test_status_response_is_normalized(enabled_client) -> None:
    manager, _fake = enabled_client
    response = manager.get("/api/labs/week01/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["healthy"] is True
    assert payload["published_port_count"] == 0
    assert payload["containers"][0]["service"] == "camera"
    assert len(payload["device_inventory"]) == 3


def test_helper_busy_error_maps_to_conflict(enabled_client) -> None:
    manager, fake = enabled_client
    fake.error = HelperError("busy", "another operation is running")
    response = manager.post("/api/labs/week01/actions/start")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "busy"


def test_command_failure_includes_result(enabled_client) -> None:
    manager, fake = enabled_client
    fake.error = HelperError(
        "command_failed",
        "start failed",
        response={"result": {"returncode": 1, "stderr": "compose failed"}},
    )
    response = manager.post("/api/labs/week01/actions/start")
    assert response.status_code == 500
    assert response.json()["detail"]["result"]["stderr"] == "compose failed"


def test_frontend_is_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "IoT Security Virtual Laboratory" in response.text
    assert client.get("/app.js").status_code == 200


def test_evidence_filename_validation() -> None:
    response = client.get("/api/labs/week01/evidence/%2E%2E%2Fetc%2Fpasswd")
    assert response.status_code in (400, 404)
