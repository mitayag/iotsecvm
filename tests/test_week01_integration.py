from __future__ import annotations

import json
import re
import time

import pytest

from conftest import (
    EVIDENCE_VOLUME,
    HELPER_IMAGE,
    IOT_NETWORK,
    MGMT_NETWORK,
    ROOT,
    SCANNER_IMAGE,
    docker_available,
    run,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not docker_available(), reason="Docker daemon is not available"),
]


def compose(*args: str, check: bool = True):
    return run(
        ["docker", "compose", "-p", "iotlab-week01", "-f", str(ROOT / "labs/week01/docker-compose.yml"), *args],
        check=check,
    )


def ps_payload() -> list[dict]:
    result = compose("ps", "--format", "json")
    text = result.stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def nmap(network: str, targets: list[str]) -> str:
    return run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
            SCANNER_IMAGE,
            "-sT",
            "-Pn",
            "-n",
            "-p",
            "22,1883,8080,8554",
            *targets,
        ],
        timeout=180,
    ).stdout


def assert_open(scan: str, ip: str, ports: list[int]) -> None:
    blocks = [block for block in re.split(r"Nmap scan report for ", scan) if block.startswith(ip)]
    assert blocks, f"no scan report for {ip}\n{scan}"
    for port in ports:
        assert re.search(rf"^{port}/tcp\s+open\b", blocks[0], re.MULTILINE), (
            f"port {port} not open on {ip}\n{blocks[0]}"
        )


def test_containers_are_healthy(lab_running: str) -> None:
    services = {item["Service"]: item for item in ps_payload()}
    assert set(services) == {"camera", "gateway", "controller"}
    for name, service in services.items():
        assert service["State"] == "running", (name, service)
        assert service.get("Health") in ("healthy", ""), (name, service)


def test_nmap_discovers_iot_devices(lab_running: str, container_ips: dict) -> None:
    camera_ip = container_ips["iotlab_w01_camera"]["ip"]
    gateway_ip = container_ips["iotlab_w01_gateway"]["ip"]

    iot_scan = nmap(IOT_NETWORK, [camera_ip, gateway_ip])
    assert_open(iot_scan, camera_ip, [8080, 8554])
    assert_open(iot_scan, gateway_ip, [1883])


def test_nmap_discovers_management_services(lab_running: str, container_ips: dict) -> None:
    controller_ip = container_ips["iotlab_w01_controller"]["ip"]
    gateway_ip = container_ips["iotlab_w01_gateway"]["mgmt_ip"]

    mgmt_scan = nmap(MGMT_NETWORK, [controller_ip, gateway_ip])
    assert_open(mgmt_scan, controller_ip, [22])
    assert_open(mgmt_scan, gateway_ip, [1883])


def test_no_services_are_published_on_host(lab_running: str) -> None:
    for service in ps_payload():
        for publisher in service.get("Publishers") or []:
            assert publisher.get("PublishedPort", 0) == 0, service

    for network in (IOT_NETWORK, MGMT_NETWORK):
        inspected = json.loads(run(["docker", "network", "inspect", network]).stdout)[0]
        assert inspected["Internal"] is True


def test_iot_network_cannot_reach_controller_or_internet(
    lab_running: str, container_ips: dict
) -> None:
    controller_ip = container_ips["iotlab_w01_controller"]["ip"]
    for target in (f"{controller_ip} 22", "1.1.1.1 443"):
        result = run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                IOT_NETWORK,
                HELPER_IMAGE,
                "sh",
                "-c",
                f"nc -z -w 3 {target}",
            ],
            check=False,
        )
        assert result.returncode != 0, f"unexpected connectivity to {target}"


def test_controller_accepts_student_key(lab_running: str) -> None:
    image = "iotlab/test-ssh-client:0.1.0"
    run(
        ["docker", "build", "-q", "-t", image, str(ROOT / "tests/images/ssh-client")],
        timeout=300,
    )
    key = ROOT / "var/secrets/week01_controller_ed25519"
    result = run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            MGMT_NETWORK,
            "-v",
            f"{key}:/key:ro",
            image,
            "-i",
            "/key",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "ConnectTimeout=5",
            "labuser@controller",
            "whoami",
        ],
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "labuser" in result.stdout


def test_mqtt_gateway_accepts_publish(lab_running: str) -> None:
    result = run(
        [
            "docker",
            "exec",
            "iotlab_w01_gateway",
            "mosquitto_pub",
            "-h",
            "127.0.0.1",
            "-t",
            "iotlab/test",
            "-m",
            "stage1",
        ]
    )
    assert result.returncode == 0


def test_reset_restores_state_and_preserves_evidence(lab_running: str) -> None:
    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            "iotlab_w01_camera_state:/state",
            HELPER_IMAGE,
            "sh",
            "-c",
            "echo state-marker > /state/reset-marker",
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
            "echo evidence-marker > /evidence/reset-evidence-marker",
        ]
    )

    run(["scripts/lab-reset.sh", "week01", "--yes"], timeout=300)
    time.sleep(2)

    state = run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            "iotlab_w01_camera_state:/state",
            HELPER_IMAGE,
            "sh",
            "-c",
            "test ! -f /state/reset-marker",
        ],
        check=False,
    )
    assert state.returncode == 0, "camera state survived reset"

    evidence = run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{EVIDENCE_VOLUME}:/evidence",
            HELPER_IMAGE,
            "sh",
            "-c",
            "test -f /evidence/reset-evidence-marker",
        ],
        check=False,
    )
    assert evidence.returncode == 0, "evidence was deleted by reset"

    for service in ps_payload():
        assert service["State"] == "running", service
