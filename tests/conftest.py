from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAB = "week01"
COMPOSE = ROOT / "labs" / LAB / "docker-compose.yml"
IOT_NETWORK = "iotlab_w01_iot"
MGMT_NETWORK = "iotlab_w01_mgmt"
EVIDENCE_VOLUME = "iotlab_w01_evidence"
HELPER_IMAGE = "alpine:3.20.3"
SCANNER_IMAGE = "instrumentisto/nmap:7.95-r0"


def run(command: list[str], *, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, check=False
    )
    return result.returncode == 0


requires_docker = pytest.mark.skipif(
    not docker_available(), reason="Docker daemon is not available"
)


def nmap_scan(network: str, targets: list[str]) -> str:
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


def build_ssh_client() -> str:
    image = "iotlab/test-ssh-client:0.1.0"
    run(
        ["docker", "build", "-q", "-t", image, str(ROOT / "tests/images/ssh-client")],
        timeout=300,
    )
    return image


def ssh_whoami(network: str, key: Path, host: str = "controller") -> subprocess.CompletedProcess:
    image = build_ssh_client()
    return run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            network,
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
            f"labuser@{host}",
            "whoami",
        ],
        check=False,
        timeout=120,
    )


@pytest.fixture(scope="session")
def lab_running() -> str:
    run(["scripts/gen-lab-keys.sh", LAB])
    if "IOTLAB_SKIP_BUILD" not in os.environ:
        run(["scripts/lab-build.sh", LAB], timeout=900)
    run(["scripts/lab-start.sh", LAB], timeout=300)
    yield LAB
    run(["scripts/lab-stop.sh", LAB], check=False)


@pytest.fixture(scope="session")
def container_ips(lab_running: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for container, network in (
        ("iotlab_w01_camera", IOT_NETWORK),
        ("iotlab_w01_gateway", IOT_NETWORK),
        ("iotlab_w01_controller", MGMT_NETWORK),
    ):
        inspected = run(["docker", "inspect", container])
        payload = json.loads(inspected.stdout)[0]
        result[container] = {
            "network": network,
            "ip": payload["NetworkSettings"]["Networks"][network]["IPAddress"],
        }
    gateway = result["iotlab_w01_gateway"]
    gateway["mgmt_ip"] = json.loads(
        run(["docker", "inspect", "iotlab_w01_gateway"]).stdout
    )[0]["NetworkSettings"]["Networks"][MGMT_NETWORK]["IPAddress"]
    return result
