#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/verify.sh [--quick] [--integration]

  --quick        Static checks only; skip Docker Compose validation and tests.
  --integration  Also run the integration test suite (requires Docker).

Checks include repository layout, manifest schema, Compose rendering, shell
syntax where shellcheck is available, and optionally the pytest suite.
EOF
}

quick=0
integration=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) quick=1 ;;
    --integration) integration=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

python_bin="$ROOT/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  python_bin="$(command -v python3 || true)"
fi
[[ -n "$python_bin" ]] || die "python3 is required"

log "checking required files"
required=(
  VERSION
  schema/lab.schema.json
  tools/validate_labs.py
  labs/week01/lab.yaml
  labs/week01/docker-compose.yml
  backend/helper/server.py
  deploy/iotlab-helper.service
  deploy/iotlab-manager.service
  deploy/iotlab-manager.desktop
  scripts/lab-start.sh
  scripts/lab-reset.sh
  scripts/lab-inspect.sh
  scripts/lab-evidence-list.sh
  scripts/lab-evidence-read.sh
  docs/adding-labs.md
  docs/deployment.md
)
for relative in "${required[@]}"; do
  [[ -e "$ROOT/$relative" ]] || die "missing required file: $relative"
done

[[ "$IOTLAB_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]] \
  || die "invalid VERSION: $IOTLAB_VERSION"

log "validating lab manifests"
if ! "$python_bin" -c 'import yaml, jsonschema' >/dev/null 2>&1; then
  die "python packages missing; run: python3 -m venv .venv && .venv/bin/pip install -r tests/requirements-dev.txt"
fi
"$python_bin" "$ROOT/tools/validate_labs.py" "$ROOT"

if command -v shellcheck >/dev/null 2>&1; then
  log "running shellcheck"
  shellcheck -x "$ROOT"/scripts/*.sh "$ROOT"/scripts/lib/*.sh
else
  warn "shellcheck not installed; skipping shell lint"
fi

if (( quick == 0 )); then
  require_docker
  log "validating Docker Compose files"
  for manifest in "$ROOT"/labs/week*/lab.yaml; do
    lab_dir="$(dirname "$manifest")"
    [[ -f "$lab_dir/docker-compose.yml" ]] || continue
    docker compose -f "$lab_dir/docker-compose.yml" config --quiet
    log "compose ok: ${lab_dir#"$ROOT"/}"
  done
fi

if (( integration == 1 )); then
  require_docker
  log "running integration tests"
  "$python_bin" -m pytest -m integration "$ROOT/tests"
fi

log "verification passed (version $IOTLAB_VERSION)"
