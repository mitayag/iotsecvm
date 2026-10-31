from __future__ import annotations

import configparser
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read(path)
    return parser


def test_version_is_semver() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)


def test_manager_unit_has_no_docker_socket() -> None:
    parser = unit(ROOT / "deploy" / "iotlab-manager.service")
    text = (ROOT / "deploy" / "iotlab-manager.service").read_text()
    assert parser["Service"]["User"] == "iotlab"
    assert parser["Service"]["Group"] == "iotlab"
    assert "127.0.0.1" in parser["Service"]["ExecStart"]
    assert "docker.sock" not in text
    assert "IOTLAB_ENABLE_ACTIONS=1" in text
    assert "IOTLAB_HELPER_SOCKET=/run/iotlab/helper.sock" in text


def test_helper_unit_is_constrained() -> None:
    parser = unit(ROOT / "deploy" / "iotlab-helper.service")
    text = (ROOT / "deploy" / "iotlab-helper.service").read_text()
    assert parser["Service"]["User"] == "root"
    assert parser["Service"]["Group"] == "iotlab"
    assert "backend.helper.server" in parser["Service"]["ExecStart"]
    assert "--socket /run/iotlab/helper.sock" in parser["Service"]["ExecStart"]
    assert "--socket-group iotlab" in parser["Service"]["ExecStart"]
    assert "__IOTLAB_UID__" in text
    assert "IOTLAB_KEY_GROUP=iotlab-students" in text
    assert "NoNewPrivileges=true" in text
    assert "ReadWritePaths=/opt/iotlab/var /run/iotlab" in text


def test_desktop_launcher_targets_localhost() -> None:
    parser = unit(ROOT / "deploy" / "iotlab-manager.desktop")
    entry = parser["Desktop Entry"]
    assert entry["Type"] == "Application"
    assert entry["Exec"] == "xdg-open http://127.0.0.1:8080"
    assert entry["Terminal"] == "false"


def test_installer_wires_helper_manager_and_desktop() -> None:
    text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "iotlab-helper.service" in text
    assert "iotlab-manager.service" in text
    assert "iotlab-manager.desktop" in text
    assert "__IOTLAB_UID__" in text
    assert "IOTLAB_KEY_GROUP=iotlab-students" in text
