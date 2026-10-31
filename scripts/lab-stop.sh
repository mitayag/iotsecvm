#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-stop.sh <week>

Stops lab containers while retaining state, evidence volumes and networks.
EOF
}

main() {
  local week="${1:-}"
  [[ -n "$week" ]] || { usage; exit 1; }
  load_lab "$week"
  require_docker
  require_compose
  log "stopping $LAB_ID"
  compose_for_lab stop
  compose_for_lab ps
}

main "$@"
