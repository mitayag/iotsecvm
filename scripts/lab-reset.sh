#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/lab-reset.sh <week> [--yes]

Stops the lab, removes state volumes labelled iotlab.role=state, then starts a
clean lab. The evidence volume and student keys are preserved.
EOF
}

main() {
  local week="${1:-}"
  local assume_yes=0
  [[ -n "$week" ]] || { usage; exit 1; }
  shift || true
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes|-y) assume_yes=1 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  load_lab "$week"
  require_docker
  require_compose
  lab_is_implemented || die "$LAB_ID is marked planned; no runtime is available"

  if (( assume_yes == 0 )); then
    printf 'Reset %s? This removes lab state but preserves evidence. [y/N] ' "$LAB_ID"
    read -r reply
    [[ "$reply" =~ ^[Yy]$ ]] || { log "reset cancelled"; exit 0; }
  fi

  log "stopping $LAB_ID and keeping evidence"
  compose_for_lab down --remove-orphans

  log "removing state volumes for $LAB_ID"
  local volumes
  volumes="$(docker volume ls -q \
    --filter "label=iotlab.lab=$LAB_ID" \
    --filter "label=iotlab.role=state")"
  if [[ -n "$volumes" ]]; then
    while IFS= read -r volume; do
      [[ -n "$volume" ]] || continue
      docker volume rm "$volume" >/dev/null
      log "removed state volume: $volume"
    done <<< "$volumes"
  else
    log "no state volumes to remove"
  fi

  if docker volume inspect "$LAB_EVIDENCE_VOLUME" >/dev/null 2>&1; then
    log "evidence preserved: $LAB_EVIDENCE_VOLUME"
  fi

  "$ROOT/scripts/networks.sh" ensure "$LAB_ID"
  ensure_lab_secrets
  mkdir -p "$ROOT/var/evidence/$LAB_ID"

  log "starting clean $LAB_ID"
  compose_for_lab up -d --wait --wait-timeout 180
  compose_for_lab ps
}

main "$@"
