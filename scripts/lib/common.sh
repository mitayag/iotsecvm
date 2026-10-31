#!/usr/bin/env bash

set -Eeuo pipefail

COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$COMMON_DIR/../.." && pwd -P)"

if [[ ! -f "$ROOT/VERSION" ]]; then
  echo "cannot locate repository root from $COMMON_DIR" >&2
  exit 1
fi

IOTLAB_VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
export IOTLAB_VERSION

log() {
  printf '[iotlab] %s\n' "$*"
}

warn() {
  printf '[iotlab] WARNING: %s\n' "$*" >&2
}

die() {
  printf '[iotlab] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

require_docker() {
  require_command docker
  docker compose version >/dev/null 2>&1 || die "docker compose v2 is required"
  docker info >/dev/null 2>&1 || die "Docker daemon is not reachable"
}

normalize_week() {
  local raw="${1:-}"
  local digits
  raw="${raw#week}"
  raw="${raw#Week}"
  raw="${raw#WEEK}"
  [[ "$raw" =~ ^[0-9]{1,2}$ ]] || die "week must be 1-18 or weekNN (got '${1:-}')"
  digits=$((10#$raw))
  (( digits >= 1 && digits <= 18 )) || die "week must be between 1 and 18"
  printf '%02d' "$digits"
}

load_lab() {
  LAB_WEEK="$(normalize_week "${1:-}")"
  LAB_ID="week${LAB_WEEK}"
  LAB_DIR="$ROOT/labs/$LAB_ID"
  # shellcheck disable=SC2034
  LAB_WEEK_NUMBER=$((10#$LAB_WEEK))
  LAB_PROJECT="iotlab-${LAB_ID}"
  # shellcheck disable=SC2034
  LAB_IOT_NETWORK="iotlab_w${LAB_WEEK}_iot"
  # shellcheck disable=SC2034
  LAB_MGMT_NETWORK="iotlab_w${LAB_WEEK}_mgmt"
  # shellcheck disable=SC2034
  LAB_EVIDENCE_VOLUME="iotlab_w${LAB_WEEK}_evidence"

  [[ -d "$LAB_DIR" ]] || die "lab directory not found: $LAB_DIR"
  [[ -f "$LAB_DIR/lab.yaml" ]] || die "lab manifest not found: $LAB_DIR/lab.yaml"
}

lab_is_implemented() {
  grep -Eq '^status:[[:space:]]*implemented[[:space:]]*$' "$LAB_DIR/lab.yaml"
}

require_compose() {
  [[ -f "$LAB_DIR/docker-compose.yml" ]] \
    || die "$LAB_ID is not implemented yet (missing docker-compose.yml)"
}

compose_for_lab() {
  docker compose -p "$LAB_PROJECT" -f "$LAB_DIR/docker-compose.yml" "$@"
}

ensure_lab_secrets() {
  "$ROOT/scripts/gen-lab-keys.sh" "$LAB_ID" >/dev/null
}

auth_keys_file() {
  printf '%s/var/secrets/%s_controller_authorized_keys\n' "$ROOT" "$LAB_ID"
}
