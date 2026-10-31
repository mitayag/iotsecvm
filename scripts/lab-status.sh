#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-status.sh <week>

Shows container health and network isolation status for a lab.
EOF
}

main() {
  local week="${1:-}"
  [[ -n "$week" ]] || { usage; exit 1; }
  load_lab "$week"
  require_docker

  printf 'Lab: %s (version %s)\n' "$LAB_ID" "$IOTLAB_VERSION"
  printf 'Compose file: %s\n' "$LAB_DIR/docker-compose.yml"

  if [[ -f "$LAB_DIR/docker-compose.yml" ]]; then
    compose_for_lab ps
  else
    printf 'Containers: not implemented\n'
  fi

  printf '\nNetworks:\n'
  "$ROOT/scripts/networks.sh" status "$LAB_ID" || true

  printf '\nEvidence volume: %s\n' "$LAB_EVIDENCE_VOLUME"
  if docker volume inspect "$LAB_EVIDENCE_VOLUME" >/dev/null 2>&1; then
    docker volume inspect \
      -f '  present=true created={{.CreatedAt}}' \
      "$LAB_EVIDENCE_VOLUME"
  else
    printf '  present=false\n'
  fi
}

main "$@"
