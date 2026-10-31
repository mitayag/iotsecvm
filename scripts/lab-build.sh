#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-build.sh <week> [docker compose build options...]

Builds images for an implemented lab. Images use the version in VERSION.
EOF
}

main() {
  local week="${1:-}"
  [[ -n "$week" ]] || { usage; exit 1; }
  shift || true
  load_lab "$week"
  require_docker
  require_compose
  lab_is_implemented || die "$LAB_ID is marked planned; build is not available"
  log "building $LAB_ID images at version $IOTLAB_VERSION"
  compose_for_lab build "$@"
}

main "$@"
