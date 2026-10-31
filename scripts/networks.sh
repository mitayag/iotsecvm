#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/networks.sh <ensure|status|remove> <week>

Creates the common per-lab internal Docker networks:
  iotlab_wNN_iot   10.231.NN.0/24
  iotlab_wNN_mgmt  10.232.NN.0/24

Networks are internal-only; Docker does not provide an external gateway.
EOF
}

network_exists() {
  docker network inspect "$1" >/dev/null 2>&1
}

ensure_network() {
  local name="$1" subnet="$2" gateway="$3"
  if network_exists "$name"; then
    local owner
    owner="$(docker network inspect -f '{{index .Labels "iotlab.lab"}}' "$name" 2>/dev/null || true)"
    [[ "$owner" == "$LAB_ID" ]] || die "network $name exists but is not owned by $LAB_ID"
    log "network ready: $name ($subnet)"
    return 0
  fi
  docker network create \
    --driver bridge \
    --internal \
    --subnet "$subnet" \
    --gateway "$gateway" \
    --label "iotlab.lab=$LAB_ID" \
    --label iotlab.managed=true \
    "$name" >/dev/null
  log "network created: $name ($subnet)"
}

remove_network() {
  local name="$1"
  if ! network_exists "$name"; then
    log "network absent: $name"
    return 0
  fi
  local attached
  attached="$(docker network inspect -f '{{len .Containers}}' "$name")"
  if [[ "$attached" != "0" ]]; then
    die "network $name still has $attached attached container(s)"
  fi
  docker network rm "$name" >/dev/null
  log "network removed: $name"
}

status_network() {
  local name="$1"
  if network_exists "$name"; then
    docker network inspect \
      -f '{{.Name}} driver={{.Driver}} internal={{.Internal}} subnet={{range .IPAM.Config}}{{.Subnet}}{{end}}' \
      "$name"
  else
    printf '%s missing\n' "$name"
    return 1
  fi
}

main() {
  local action="${1:-}" week="${2:-}"
  if [[ -z "$action" || -z "$week" ]]; then
    usage
    exit 1
  fi
  load_lab "$week"
  require_command docker
  docker info >/dev/null 2>&1 || die "Docker daemon is not reachable"

  local iot_octet=$((LAB_WEEK_NUMBER))
  local mgmt_octet=$((LAB_WEEK_NUMBER))
  local iot_subnet="10.231.${iot_octet}.0/24"
  local mgmt_subnet="10.232.${mgmt_octet}.0/24"

  case "$action" in
    ensure)
      ensure_network "$LAB_IOT_NETWORK" "$iot_subnet" "10.231.${iot_octet}.1"
      ensure_network "$LAB_MGMT_NETWORK" "$mgmt_subnet" "10.232.${mgmt_octet}.1"
      ;;
    status)
      local rc=0
      status_network "$LAB_IOT_NETWORK" || rc=1
      status_network "$LAB_MGMT_NETWORK" || rc=1
      return "$rc"
      ;;
    remove)
      remove_network "$LAB_IOT_NETWORK"
      remove_network "$LAB_MGMT_NETWORK"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
