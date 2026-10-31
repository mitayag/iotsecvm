#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-start.sh <week> [--build]

Ensures per-lab internal networks and student keys exist, then starts the lab
and waits for container health checks.
EOF
}

main() {
  local week="${1:-}"
  local do_build=0
  [[ -n "$week" ]] || { usage; exit 1; }
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --build) do_build=1 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  load_lab "$week"
  require_docker
  require_compose
  lab_is_implemented || die "$LAB_ID is marked planned; no runtime is available"

  "$ROOT/scripts/networks.sh" ensure "$LAB_ID"
  ensure_lab_secrets

  mkdir -p "$ROOT/var/evidence/$LAB_ID"
  chmod 0770 "$ROOT/var/evidence/$LAB_ID" 2>/dev/null || true

  if (( do_build == 1 )); then
    compose_for_lab build
  fi

  log "starting $LAB_ID at version $IOTLAB_VERSION"
  compose_for_lab up -d --wait --wait-timeout 180
  compose_for_lab ps
}

main "$@"
