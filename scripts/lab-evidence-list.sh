#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-evidence-list.sh <week>

Lists files in the preserved evidence volume as tab-separated name, size and
modification time. Prints nothing when the volume does not exist yet.
EOF
}

main() {
  local week="${1:-}"
  [[ -n "$week" ]] || { usage; exit 1; }
  load_lab "$week"
  require_docker

  if ! docker volume inspect "$LAB_EVIDENCE_VOLUME" >/dev/null 2>&1; then
    exit 0
  fi

  docker run --rm --network none \
    -v "$LAB_EVIDENCE_VOLUME:/evidence:ro" \
    alpine:3.20.3 sh -c '
      for file in /evidence/*; do
        [ -f "$file" ] || continue
        printf "%s\t%s\t%s\n" \
          "$(basename "$file")" \
          "$(stat -c %s "$file")" \
          "$(stat -c %Y "$file")"
      done
    '
}

main "$@"
