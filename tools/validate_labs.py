#!/usr/bin/env python3
"""Validate lab manifests, Compose files and Stage 1 safety invariants."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "lab.schema.json"
LABS_DIR = ROOT / "labs"
WEEK_RE = re.compile(r"^week(0[1-9]|1[0-8])$")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def load_yaml(path: Path, report: Report) -> dict | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report.error(f"{path.relative_to(ROOT)}: cannot read YAML: {exc}")
        return None
    if not isinstance(data, dict):
        report.error(f"{path.relative_to(ROOT)}: document must be a mapping")
        return None
    return data


def check_compose(
    lab_dir: Path, manifest: dict, report: Report, schema: dict
) -> None:
    compose_path = lab_dir / "docker-compose.yml"
    implemented = manifest["status"] == "implemented"
    if not compose_path.is_file():
        if implemented:
            report.error(f"{lab_dir.name}: implemented lab has no docker-compose.yml")
        return
    if not implemented:
        report.warn(f"{lab_dir.name}: planned lab already has a Compose file")

    compose = load_yaml(compose_path, report)
    if compose is None:
        return

    services = compose.get("services")
    if not isinstance(services, dict) or not services:
        report.error(f"{lab_dir.name}: Compose file has no services")
        return

    containers = {item["name"]: item for item in manifest.get("containers", [])}
    if set(services) != set(containers):
        report.error(
            f"{lab_dir.name}: Compose services {sorted(services)} do not match "
            f"manifest containers {sorted(containers)}"
        )

    for name, service in services.items():
        if not isinstance(service, dict):
            report.error(f"{lab_dir.name}: service {name} is not a mapping")
            continue
        if "ports" in service:
            report.error(f"{lab_dir.name}/{name}: host port publishing is forbidden")
        if service.get("privileged") is True:
            report.error(f"{lab_dir.name}/{name}: privileged is forbidden")
        if service.get("network_mode") == "host":
            report.error(f"{lab_dir.name}/{name}: host networking is forbidden")
        for forbidden in ("pid", "ipc", "userns_mode"):
            if service.get(forbidden) == "host":
                report.error(f"{lab_dir.name}/{name}: {forbidden}: host is forbidden")
        if "docker.sock" in json.dumps(service):
            report.error(f"{lab_dir.name}/{name}: Docker socket mount is forbidden")

        image = service.get("image", "")
        if isinstance(image, str):
            if image.endswith(":latest") or (
                ":" not in image.rsplit("/", 1)[-1] and "${" not in image
            ):
                report.error(f"{lab_dir.name}/{name}: image must use a pinned version")
            base = image.split(":${", 1)[0]
            declared = containers.get(name, {}).get("image")
            if declared and base != declared:
                report.error(
                    f"{lab_dir.name}/{name}: image {base} does not match manifest {declared}"
                )

        networks = service.get("networks", [])
        if isinstance(networks, dict):
            networks = list(networks)
        if not isinstance(networks, list):
            report.error(f"{lab_dir.name}/{name}: networks must be a list")
        else:
            for network in networks:
                if network not in ("iot", "mgmt"):
                    report.error(f"{lab_dir.name}/{name}: unknown network {network}")

    compose_networks = compose.get("networks", {})
    for key in ("iot", "mgmt"):
        expected = manifest["networks"][key]["name"]
        configured = compose_networks.get(key, {})
        if not isinstance(configured, dict):
            report.error(f"{lab_dir.name}: network {key} is not a mapping")
            continue
        if configured.get("name") != expected:
            report.error(
                f"{lab_dir.name}: network {key} should be {expected}, "
                f"found {configured.get('name')}"
            )
        if configured.get("external") is not True:
            report.error(f"{lab_dir.name}: network {key} must be external")

    declared_volumes = compose.get("volumes", {})
    for key, volume in declared_volumes.items():
        if not isinstance(volume, dict):
            continue
        labels = volume.get("labels", {})
        if isinstance(labels, dict) and labels.get("iotlab.role") == "evidence":
            if not str(volume.get("name", "")).endswith("_evidence"):
                report.error(f"{lab_dir.name}: evidence volume must end with _evidence")
    if not any(
        isinstance(volume, dict)
        and volume.get("labels", {}).get("iotlab.role") == "evidence"
        for volume in declared_volumes.values()
    ):
        report.error(f"{lab_dir.name}: no evidence volume declared")

    expected_services = {item["container"] for item in manifest["expected_services"]}
    for container in expected_services:
        if container not in services:
            report.error(
                f"{lab_dir.name}: expected service references unknown container {container}"
            )


def check_manifest(lab_dir: Path, report: Report, schema: dict) -> dict | None:
    manifest_path = lab_dir / "lab.yaml"
    manifest = load_yaml(manifest_path, report)
    if manifest is None:
        return None

    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        report.error(f"{manifest_path.relative_to(ROOT)}: {location}: {error.message}")

    if manifest.get("id") != lab_dir.name:
        report.error(f"{lab_dir.name}: id must match directory name")
    if WEEK_RE.match(str(manifest.get("id", ""))):
        if manifest.get("week") != int(lab_dir.name[-2:]):
            report.error(f"{lab_dir.name}: week does not match directory name")

    safety = manifest.get("safety", {})
    if safety.get("external_ports"):
        report.error(f"{lab_dir.name}: external_ports must be empty")
    if safety.get("privileged") is not False:
        report.error(f"{lab_dir.name}: safety.privileged must be false")
    if safety.get("host_network") is not False:
        report.error(f"{lab_dir.name}: safety.host_network must be false")
    if "evidence" not in manifest.get("reset", {}).get("preserve", []):
        report.error(f"{lab_dir.name}: reset must preserve evidence")

    if manifest.get("status") == "implemented":
        if not manifest.get("containers"):
            report.error(f"{lab_dir.name}: implemented lab needs containers")
        if not manifest.get("expected_services"):
            report.error(f"{lab_dir.name}: implemented lab needs expected services")

    ports_by_container: dict[str, set[int]] = {}
    for container in manifest.get("containers", []):
        ports_by_container[container["name"]] = set(container.get("internal_ports", []))
        if container.get("privileged") is not False:
            report.error(f"{lab_dir.name}/{container['name']}: privileged must be false")
        if container.get("host_network") is not False:
            report.error(f"{lab_dir.name}/{container['name']}: host_network must be false")

    for service in manifest.get("expected_services", []):
        declared = ports_by_container.get(service["container"], set())
        if service["port"] not in declared:
            report.error(
                f"{lab_dir.name}: expected service {service['name']} port "
                f"{service['port']} is not declared by {service['container']}"
            )

    network = manifest.get("networks", {})
    for key, expected_prefix in (("iot", "iot"), ("mgmt", "mgmt")):
        item = network.get(key, {})
        if item.get("name") != f"iotlab_w{lab_dir.name[-2:]}_{expected_prefix}":
            report.error(f"{lab_dir.name}: network {key} name is inconsistent")
        if item.get("internal") is not True:
            report.error(f"{lab_dir.name}: network {key} must be internal")
        subnet = item.get("subnet", "")
        if not subnet.startswith(("10.231.", "10.232.")):
            report.error(f"{lab_dir.name}: network {key} must use the 10.231/10.232 range")

    return manifest


def check_dockerfiles(report: Report) -> None:
    for dockerfile in sorted((ROOT / "labs").glob("week*/images/*/Dockerfile")):
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.upper().startswith("FROM "):
                continue
            image = stripped.split()[1]
            if image == "scratch":
                continue
            if image.endswith(":latest") or ":" not in image.rsplit("/", 1)[-1]:
                report.error(
                    f"{dockerfile.relative_to(ROOT)}: base image must be pinned: {image}"
                )


def main() -> int:
    report = Report()
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot load schema: {exc}", file=sys.stderr)
        return 2

    lab_dirs = sorted(
        path.parent for path in LABS_DIR.glob("week*/lab.yaml") if WEEK_RE.match(path.parent.name)
    )
    found = {path.name for path in lab_dirs}
    expected = {f"week{number:02d}" for number in range(1, 19)}
    for missing in sorted(expected - found):
        report.error(f"missing lab manifest for {missing}")

    validated = 0
    for lab_dir in lab_dirs:
        manifest = check_manifest(lab_dir, report, schema)
        if manifest is not None:
            validated += 1
            check_compose(lab_dir, manifest, report, schema)

    check_dockerfiles(report)

    for warning in report.warnings:
        print(f"WARN  {warning}")
    for error in report.errors:
        print(f"ERROR {error}")

    if report.errors:
        print(f"\nvalidation failed with {len(report.errors)} error(s)", file=sys.stderr)
        return 1
    print(
        f"validated {validated} lab manifest(s), {len(report.warnings)} warning(s), "
        "0 errors"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
