#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-evidence-read.sh <week> <filename>

Reads one text evidence file from the preserved evidence volume. File names are
restricted to a safe character set and path traversal is rejected.
EOF
}

main() {
  local week="${1:-}"
  local filename="${2:-}"
  if [[ -z "$week" || -z "$filename" ]]; then
    usage
    exit 1
  fi
  load_lab "$week"

  if [[ ! "$filename" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
    die "invalid evidence filename"
  fi
  case "$filename" in
    *..*) die "path traversal is forbidden" ;;
  esac

  require_docker
  if ! docker volume inspect "$LAB_EVIDENCE_VOLUME" >/dev/null 2>&1; then
    die "evidence volume does not exist"
  fi

  docker run --rm --network none \
    -v "$LAB_EVIDENCE_VOLUME:/evidence:ro" \
    alpine:3.20.3 sh -c 'head -c 32768 "/evidence/$1"' sh "$filename"
}

main "$@"
