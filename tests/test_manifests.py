from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_all_eighteen_weeks_exist() -> None:
    labs = sorted((ROOT / "labs").glob("week*/lab.yaml"))
    assert len(labs) == 18
    assert [path.parent.name for path in labs] == [
        f"week{number:02d}" for number in range(1, 19)
    ]


def test_manifest_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_labs.py"), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 errors" in result.stdout


def test_week01_manifest_safety_invariants() -> None:
    manifest = yaml.safe_load((ROOT / "labs" / "week01" / "lab.yaml").read_text())
    assert manifest["status"] == "implemented"
    assert manifest["safety"]["privileged"] is False
    assert manifest["safety"]["host_network"] is False
    assert manifest["safety"]["external_ports"] == []
    assert manifest["networks"]["iot"]["internal"] is True
    assert manifest["networks"]["mgmt"]["internal"] is True
    assert "evidence" in manifest["reset"]["preserve"]
    assert {item["name"] for item in manifest["containers"]} == {
        "camera",
        "gateway",
        "controller",
    }
    assert {item["port"] for item in manifest["expected_services"]} == {
        8080,
        8554,
        1883,
        22,
    }
