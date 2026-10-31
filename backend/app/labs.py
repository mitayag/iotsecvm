from __future__ import annotations

import re
from pathlib import Path

import yaml
from fastapi import HTTPException

from .settings import Settings

LAB_PATTERN = re.compile(r"^week(0[1-9]|1[0-8])$")
MAX_HOST_EVIDENCE_BYTES = 32768


def _lab_dir(settings: Settings, lab_id: str) -> Path:
    if not LAB_PATTERN.match(lab_id):
        raise HTTPException(status_code=404, detail="lab not found")
    path = settings.labs_dir / lab_id
    if not (path / "lab.yaml").is_file():
        raise HTTPException(status_code=404, detail="lab not found")
    return path


def load_lab(settings: Settings, lab_id: str) -> dict:
    path = _lab_dir(settings, lab_id) / "lab.yaml"
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=500, detail=f"invalid lab manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=500, detail="invalid lab manifest")
    return manifest


def availability(settings: Settings, manifest: dict) -> str:
    compose = settings.labs_dir / manifest["id"] / "docker-compose.yml"
    if manifest.get("status") == "implemented" and compose.is_file():
        return "available"
    return "planned"


def inventory(manifest: dict) -> list[dict]:
    services = manifest.get("expected_services", [])
    devices = []
    for container in manifest.get("containers", []):
        name = container["name"]
        devices.append(
            {
                "name": name,
                "role": container.get("role", "service"),
                "description": container.get("description", ""),
                "networks": container.get("networks", []),
                "ports": container.get("internal_ports", []),
                "services": [
                    {
                        "name": service["name"],
                        "port": service["port"],
                        "protocol": service["protocol"],
                    }
                    for service in services
                    if service.get("container") == name
                ],
            }
        )
    return devices


def summary(settings: Settings, manifest: dict) -> dict:
    lab_id = manifest["id"]
    return {
        "id": lab_id,
        "week": manifest["week"],
        "title": manifest["title"],
        "status": manifest["status"],
        "module_type": manifest.get("module_type", "lab"),
        "availability": availability(settings, manifest),
        "summary": manifest["summary"],
        "difficulty": manifest["difficulty"],
        "duration_minutes": manifest["duration_minutes"],
        "learning_objectives": manifest["learning_objectives"],
        "services": [
            {
                "name": service["name"],
                "port": service["port"],
                "protocol": service["protocol"],
                "description": service.get("description", ""),
            }
            for service in manifest.get("expected_services", [])
        ],
        "compose_present": (settings.labs_dir / lab_id / "docker-compose.yml").is_file(),
        "evidence_path": manifest["evidence"]["path"],
    }


def detail(settings: Settings, manifest: dict) -> dict:
    payload = summary(settings, manifest)
    payload.update(
        {
            "containers": manifest.get("containers", []),
            "expected_services": manifest.get("expected_services", []),
            "device_inventory": inventory(manifest),
            "networks": manifest.get("networks", {}),
            "reset": manifest.get("reset", {}),
            "safety": manifest.get("safety", {}),
        }
    )
    return payload


def list_labs(settings: Settings) -> list[dict]:
    labs = []
    for path in sorted(settings.labs_dir.glob("week*/lab.yaml")):
        if not LAB_PATTERN.match(path.parent.name):
            continue
        try:
            labs.append(summary(settings, load_lab(settings, path.parent.name)))
        except HTTPException:
            continue
    return labs


def instructions(settings: Settings, lab_id: str) -> dict:
    manifest = load_lab(settings, lab_id)
    lab_dir = settings.labs_dir / lab_id
    readme = lab_dir / "README.md"
    if readme.is_file():
        content = readme.read_text(encoding="utf-8")
        source = "README.md"
    else:
        content = (
            f"# Week {manifest['week']:02d}: {manifest['title']}\n\n"
            f"{manifest['summary']}\n\n"
            "This module is planned and has no student runtime yet.\n"
        )
        source = "lab.yaml"
    return {
        "id": lab_id,
        "title": manifest["title"],
        "format": "markdown",
        "source": source,
        "content": content,
    }


def _host_files(directory: Path) -> list[dict]:
    if not directory.is_dir():
        return []
    files = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        files.append(
            {
                "name": entry.name,
                "size": stat.st_size,
                "modified": int(stat.st_mtime),
            }
        )
    return files


def host_evidence(settings: Settings, lab_id: str) -> dict:
    manifest = load_lab(settings, lab_id)
    directory = settings.evidence_dir / lab_id
    return {
        "lab": lab_id,
        "path": manifest["evidence"]["path"],
        "host_directory": str(directory),
        "host_files": _host_files(directory),
        "expected_artifacts": manifest["evidence"]["artifacts"],
    }


def read_host_evidence(settings: Settings, lab_id: str, filename: str) -> str | None:
    directory = (settings.evidence_dir / lab_id).resolve()
    candidate = (directory / filename).resolve()
    if candidate.parent != directory or not candidate.is_file():
        return None
    if candidate.stat().st_size > MAX_HOST_EVIDENCE_BYTES:
        with candidate.open("rb") as handle:
            return handle.read(MAX_HOST_EVIDENCE_BYTES).decode("utf-8", "replace")
    return candidate.read_text(encoding="utf-8", errors="replace")
