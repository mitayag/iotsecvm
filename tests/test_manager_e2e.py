from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_helper
from backend.app.main import app
from backend.app.settings import SETTINGS, get_settings
from backend.helper.client import HelperClient
from conftest import (
    EVIDENCE_VOLUME,
    HELPER_IMAGE,
    IOT_NETWORK,
    MGMT_NETWORK,
    ROOT,
    assert_open,
    docker_available,
    nmap_scan,
    run,
    ssh_whoami,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not docker_available(), reason="Docker daemon is not available"),
]

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CAMERA_STATE = "iotlab_w01_camera_state"
CAMERA_IMAGE = f"iotlab/week01-camera:{VERSION}"


def wait_for_helper(socket_path: Path, process: subprocess.Popen) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("helper exited during startup")
        try:
            HelperClient(socket_path, timeout=2).health()
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("helper did not become ready")


@pytest.fixture(scope="module")
def manager():
    run(["scripts/lab-stop.sh", "week01"], check=False)
    run(["scripts/gen-lab-keys.sh", "week01"])
    image_check = run(["docker", "image", "inspect", CAMERA_IMAGE], check=False)
    if image_check.returncode != 0:
        run(["scripts/lab-build.sh", "week01"], timeout=900)

    directory = Path(tempfile.mkdtemp(prefix="iotlab-mgr-", dir="/tmp"))
    socket_path = directory / "h.sock"
    log_path = directory / "helper.log"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "backend.helper.server",
            "--root",
            str(ROOT),
            "--socket",
            str(socket_path),
            "--allowed-uid",
            str(os.getuid()),
        ],
        cwd=ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    wait_for_helper(socket_path, process)

    settings = replace(
        SETTINGS,
        enable_actions=True,
        helper_socket=socket_path,
        helper_timeout=330,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_helper] = lambda: HelperClient(
        socket_path, timeout=330
    )
    try:
        yield TestClient(app), socket_path
    finally:
        run(["scripts/lab-stop.sh", "week01"], check=False)
        app.dependency_overrides.clear()
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)
        log_handle.close()
        shutil.rmtree(directory, ignore_errors=True)


def container_ips() -> dict[str, str]:
    def address(container: str, network: str) -> str:
        payload = json.loads(run(["docker", "inspect", container]).stdout)[0]
        return payload["NetworkSettings"]["Networks"][network]["IPAddress"]

    return {
        "camera": address("iotlab_w01_camera", IOT_NETWORK),
        "gateway_iot": address("iotlab_w01_gateway", IOT_NETWORK),
        "gateway_mgmt": address("iotlab_w01_gateway", MGMT_NETWORK),
        "controller": address("iotlab_w01_controller", MGMT_NETWORK),
    }


def volume_file_exists(volume: str, path: str) -> bool:
    result = run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{volume}:/data",
            HELPER_IMAGE,
            "test",
            "-f",
            f"/data/{path}",
        ],
        check=False,
    )
    return result.returncode == 0


def test_manager_end_to_end(manager) -> None:
    client, _socket = manager

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["actions_enabled"] is True
    assert health.json()["helper"]["helper_available"] is True

    labs = client.get("/api/labs").json()["labs"]
    assert len(labs) == 18
    assert any(lab["module_type"] == "assessment" for lab in labs)

    start = client.post("/api/labs/week01/actions/start")
    assert start.status_code == 200, start.text
    assert start.json()["status"] == "ok"

    status = client.get("/api/labs/week01/status")
    assert status.status_code == 200, status.text
    status_payload = status.json()
    assert status_payload["healthy"] is True
    assert status_payload["published_port_count"] == 0
    assert {container["service"] for container in status_payload["containers"]} == {
        "camera",
        "gateway",
        "controller",
    }

    camera = run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            IOT_NETWORK,
            HELPER_IMAGE,
            "wget",
            "-qO-",
            "http://camera:8080/status",
        ]
    )
    assert "VC-100" in camera.stdout

    mqtt = run(
        [
            "docker",
            "exec",
            "iotlab_w01_gateway",
            "mosquitto_pub",
            "-h",
            "127.0.0.1",
            "-t",
            "iotlab/manager-e2e",
            "-m",
            "ok",
        ]
    )
    assert mqtt.returncode == 0

    ips = container_ips()
    iot_scan = nmap_scan(IOT_NETWORK, [ips["camera"], ips["gateway_iot"]])
    assert_open(iot_scan, ips["camera"], [8080, 8554])
    assert_open(iot_scan, ips["gateway_iot"], [1883])

    mgmt_scan = nmap_scan(MGMT_NETWORK, [ips["controller"], ips["gateway_mgmt"]])
    assert_open(mgmt_scan, ips["controller"], [22])
    assert_open(mgmt_scan, ips["gateway_mgmt"], [1883])

    ssh = ssh_whoami(
        MGMT_NETWORK, ROOT / "var/secrets/week01_controller_ed25519"
    )
    assert ssh.returncode == 0, ssh.stderr
    assert "labuser" in ssh.stdout

    detail = client.get("/api/labs/week01").json()
    assert {item["name"] for item in detail["device_inventory"]} == {
        "camera",
        "gateway",
        "controller",
    }
    assert {item["port"] for item in detail["expected_services"]} == {
        22,
        1883,
        8080,
        8554,
    }

    instructions = client.get("/api/labs/week01/instructions")
    assert instructions.status_code == 200
    assert "Week 01" in instructions.json()["content"]

    evidence = client.get("/api/labs/week01/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["runtime_available"] is True
    runtime_names = {item["name"] for item in evidence.json()["runtime_files"]}
    assert "camera-events.log" in runtime_names

    event_file = client.get("/api/labs/week01/evidence/camera-events.log")
    assert event_file.status_code == 200
    assert event_file.json()["source"] == "runtime"
    assert "startup" in event_file.json()["content"]

    stop = client.post("/api/labs/week01/actions/stop")
    assert stop.status_code == 200, stop.text
    stopped = client.get("/api/labs/week01/status").json()
    assert stopped["containers"] == []
    assert stopped["healthy"] is False

    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{CAMERA_STATE}:/state",
            HELPER_IMAGE,
            "sh",
            "-c",
            "echo state-marker > /state/manager-reset-marker",
        ]
    )
    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{EVIDENCE_VOLUME}:/evidence",
            HELPER_IMAGE,
            "sh",
            "-c",
            "echo evidence-marker > /evidence/manager-reset-evidence",
        ]
    )

    reset = client.post("/api/labs/week01/actions/reset")
    assert reset.status_code == 200, reset.text
    reset_status = client.get("/api/labs/week01/status").json()
    assert reset_status["healthy"] is True
    assert not volume_file_exists(CAMERA_STATE, "manager-reset-marker")
    assert volume_file_exists(EVIDENCE_VOLUME, "manager-reset-evidence")

    preserved = client.get("/api/labs/week01/evidence/manager-reset-evidence")
    assert preserved.status_code == 200
    assert "evidence-marker" in preserved.json()["content"]

    final_stop = client.post("/api/labs/week01/actions/stop")
    assert final_stop.status_code == 200

    remaining = run(
        ["docker", "ps", "--filter", "label=iotlab.lab=week01", "--format", "{{.Names}}"]
    )
    assert remaining.stdout.strip() == ""
