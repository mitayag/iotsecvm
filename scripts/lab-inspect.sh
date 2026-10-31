#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-inspect.sh <week>

Prints the Docker Compose container status as JSON. Intended for the privileged
helper; it does not accept arbitrary Compose paths.
EOF
}

main() {
  local week="${1:-}"
  [[ -n "$week" ]] || { usage; exit 1; }
  load_lab "$week"
  require_docker
  require_compose

  local output
  output="$(compose_for_lab ps --format json)"
  if [[ -z "$output" ]]; then
    printf '[]\n'
  else
    printf '%s\n' "$output"
  fi
}

main "$@"
