from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "labs" / "week01" / "docker-compose.yml"


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_compose_config_renders() -> None:
    result = __import__("subprocess").run(
        ["docker", "compose", "-f", str(COMPOSE), "config", "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_compose_has_no_host_publication_or_privileges() -> None:
    compose = yaml.safe_load(COMPOSE.read_text())
    for name, service in compose["services"].items():
        assert "ports" not in service, f"{name} publishes ports"
        assert service.get("privileged") is not True
        assert service.get("network_mode") != "host"
    assert compose["networks"]["iot"]["external"] is True
    assert compose["networks"]["mgmt"]["external"] is True
    assert compose["volumes"]["evidence"]["labels"]["iotlab.role"] == "evidence"


def test_container_images_are_versioned() -> None:
    compose = yaml.safe_load(COMPOSE.read_text())
    for service in compose["services"].values():
        image = service["image"]
        assert ":latest" not in image
        assert "${IOTLAB_VERSION" in image
