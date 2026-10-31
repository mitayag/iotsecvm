#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-evidence.sh <list|export|import> <week> [path]

  list   <week>          List files in the preserved evidence volume.
  export <week> <dir>    Copy evidence into a host directory (created if needed).
  import <week> <file>   Copy a host file into the evidence volume.

Host directory mirror: var/evidence/<week> is also available for host-side notes
and is never deleted by reset or update.
EOF
}

require_evidence_volume() {
  docker volume inspect "$LAB_EVIDENCE_VOLUME" >/dev/null 2>&1 \
    || die "evidence volume $LAB_EVIDENCE_VOLUME does not exist; start the lab first"
}

main() {
  local action="${1:-}" week="${2:-}" target="${3:-}"
  if [[ -z "$action" || -z "$week" ]]; then
    usage
    exit 1
  fi
  load_lab "$week"
  require_docker
  require_evidence_volume

  local helper_image="alpine:3.20.3"

  case "$action" in
    list)
      docker run --rm -v "$LAB_EVIDENCE_VOLUME:/evidence:ro" "$helper_image" \
        ls -la /evidence
      ;;
    export)
      [[ -n "$target" ]] || { usage; exit 1; }
      local cid
      cid="$(docker create -v "$LAB_EVIDENCE_VOLUME:/evidence:ro" "$helper_image" true)"
      mkdir -p "$target"
      docker cp "$cid:/evidence/." "$target/"
      docker rm -f "$cid" >/dev/null
      log "evidence exported to $target"
      ;;
    import)
      [[ -n "$target" && -f "$target" ]] || die "import source file not found"
      local cid name
      name="$(basename "$target")"
      cid="$(docker create -v "$LAB_EVIDENCE_VOLUME:/evidence" "$helper_image" true)"
      docker cp "$target" "$cid:/evidence/$name"
      docker rm -f "$cid" >/dev/null
      log "evidence imported: $name"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
