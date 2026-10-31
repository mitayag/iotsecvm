import re
from pathlib import Path

import yaml
from fastapi import HTTPException

from .settings import LABS_DIR

LAB_PATTERN = re.compile(r"^week(0[1-9]|1[0-8])$")


def _manifest_path(lab_id: str) -> Path:
    if not LAB_PATTERN.match(lab_id):
        raise HTTPException(status_code=404, detail="lab not found")
    path = LABS_DIR / lab_id / "lab.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="lab not found")
    return path


def load_lab(lab_id: str) -> dict:
    path = _manifest_path(lab_id)
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=500, detail=f"invalid lab manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise HTTPException(status_code=500, detail="invalid lab manifest")
    return manifest


def summary(manifest: dict) -> dict:
    lab_id = manifest["id"]
    return {
        "id": lab_id,
        "week": manifest["week"],
        "title": manifest["title"],
        "status": manifest["status"],
        "summary": manifest["summary"],
        "difficulty": manifest["difficulty"],
        "duration_minutes": manifest["duration_minutes"],
        "learning_objectives": manifest["learning_objectives"],
        "services": [
            {
                "name": service["name"],
                "port": service["port"],
                "protocol": service["protocol"],
            }
            for service in manifest.get("expected_services", [])
        ],
        "compose_present": (LABS_DIR / lab_id / "docker-compose.yml").is_file(),
        "evidence_path": manifest["evidence"]["path"],
    }


def list_labs() -> list[dict]:
    labs = []
    for path in sorted(LABS_DIR.glob("week*/lab.yaml")):
        if not LAB_PATTERN.match(path.parent.name):
            continue
        try:
            labs.append(summary(load_lab(path.parent.name)))
        except HTTPException:
            continue
    return labs
