#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

DEST="${IOTLAB_HOME:-/opt/iotlab}"
BUNDLE=""
EXPECTED_SHA256=""
SKIP_INSTALL=0
STUDENT_USER="student"
REPORT=""
PASS_COUNT=0
WARN_COUNT=0
COMPOSE_VERSION=""
OS_PRETTY=""

usage() {
  cat <<'EOF'
Usage: sudo scripts/acceptance-ubuntu.sh [options]

Run on a disposable Ubuntu 24.04 LTS x86-64 VM.

  --bundle FILE         Offline bundle to install and test
  --sha256 HEX          Expected SHA256 of the bundle file
  --dest DIR            Installation home (default: /opt/iotlab)
  --skip-install        Test the existing installation; do not install
  --student-user USER   Login account expected in iotlab-students (default: student)
  --report FILE         Markdown report path
  -h, --help            Show this help

This script refuses to run outside Ubuntu 24.04 x86-64 or without root.
It installs services, starts Week 1 through the Lab Manager, runs HTTP, MQTT,
SSH, Nmap, status, stop, reset and evidence checks, and writes a Markdown report.
EOF
}

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '| %s | PASS | %s |\n' "$1" "${2:-}"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '| %s | WARN | %s |\n' "$1" "${2:-}"
}

fail() {
  printf '| %s | **FAIL** | %s |\n' "$1" "${2:-}"
  printf '\nAcceptance failed at %s.\n' "$(timestamp)"
  exit 1
}

section() {
  printf '\n### %s\n\n| Check | Result | Detail |\n| --- | --- | --- |\n' "$1"
}

api_get() {
  curl -fsS "http://127.0.0.1:8080$1"
}

api_post() {
  curl -fsS -X POST "http://127.0.0.1:8080$1"
}

container_ip() {
  docker inspect -f "{{(index .NetworkSettings.Networks \"$2\").IPAddress}}" "$1"
}

assert_nmap_open() {
  local name="$1" ip="$2" port="$3" scan="$4"
  if printf '%s\n' "$scan" | grep "Host: ${ip} " | grep -q "${port}/open"; then
    pass "$name" "${ip}:${port} open"
  else
    fail "$name" "${ip}:${port} was not open"
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --bundle) BUNDLE="${2:-}"; shift ;;
      --sha256) EXPECTED_SHA256="${2:-}"; shift ;;
      --dest) DEST="${2:-}"; shift ;;
      --skip-install) SKIP_INSTALL=1 ;;
      --student-user) STUDENT_USER="${2:-}"; shift ;;
      --report) REPORT="${2:-}"; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done
  if (( SKIP_INSTALL == 1 )) && [[ -n "$BUNDLE" ]]; then
    die "--bundle and --skip-install cannot be combined"
  fi
}

check_host() {
  [[ "$(id -u)" == "0" ]] || die "run this acceptance test as root (sudo)"
  if [[ ! -r /etc/os-release ]]; then
    die "cannot read /etc/os-release"
  fi
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || die "Ubuntu is required (found ${ID:-unknown})"
  [[ "${VERSION_ID:-}" == "24.04" ]] \
    || die "Ubuntu 24.04 LTS is required (found ${VERSION_ID:-unknown})"
  [[ "$(uname -m)" == "x86_64" ]] \
    || die "x86-64 is required (found $(uname -m))"

  for command in docker curl python3 systemctl stat sha256sum tar; do
    command -v "$command" >/dev/null 2>&1 || die "missing command: $command"
  done
  COMPOSE_VERSION="$(docker compose version --short 2>/dev/null || true)"
  [[ -n "$COMPOSE_VERSION" ]] || die "Docker Compose v2 is required"
  docker info >/dev/null 2>&1 || die "Docker daemon is not reachable"
  OS_PRETTY="${PRETTY_NAME}"
}

install_under_test() {
  if (( SKIP_INSTALL == 1 )); then
    [[ -L "$DEST/current" ]] || fail "Existing installation" "$DEST/current is missing"
    pass "Existing installation" "$DEST/current"
    return 0
  fi

  local source_dir="$ROOT"
  local staging=""
  if [[ -n "$BUNDLE" ]]; then
    [[ -f "$BUNDLE" ]] || fail "Offline bundle" "file not found: $BUNDLE"
    if [[ -n "$EXPECTED_SHA256" ]]; then
      local actual_sha
      actual_sha="$(sha256sum "$BUNDLE" | awk '{print $1}')"
      [[ "$actual_sha" == "$EXPECTED_SHA256" ]] \
        || fail "Bundle checksum" "expected $EXPECTED_SHA256, found $actual_sha"
      pass "Bundle checksum" "$actual_sha"
    fi
    staging="$(mktemp -d "${TMPDIR:-/tmp}/iotlab-acceptance.XXXXXX")"
    tar -C "$staging" -xf "$BUNDLE"
    (cd "$staging" && sha256sum -c SHA256SUMS >/dev/null) \
      || fail "Bundle internal checksums" "SHA256SUMS verification failed"
    pass "Bundle internal checksums" "SHA256SUMS verified"
    source_dir="$(find "$staging" -maxdepth 2 -type f -name VERSION -print | head -n 1 | xargs dirname)"
    [[ -n "$source_dir" ]] || fail "Bundle source" "release directory missing"
    "$source_dir/scripts/install.sh" \
      --dest "$DEST" \
      --offline-images "$staging/images/iotlab-images.tar" \
      --wheelhouse "$staging/wheels" \
      --yes
  else
    "$ROOT/scripts/install.sh" --dest "$DEST" --yes
  fi

  if [[ -n "$staging" ]]; then
    rm -rf "$staging"
  fi
  [[ -x "$DEST/current/scripts/acceptance-ubuntu.sh" ]] \
    || warn "Installed release" "acceptance script is not present in the release"
  pass "Installation" "$DEST/current"
}

check_services() {
  local service
  for service in iotlab-helper.service iotlab-manager.service; do
    if systemctl is-active --quiet "$service"; then
      pass "Service $service" "active"
    else
      fail "Service $service" "not active; inspect journalctl -u $service"
    fi
  done

  for _ in $(seq 1 60); do
    if api_get /api/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  local health
  health="$(api_get /api/health)" || fail "Lab Manager API" "health endpoint unreachable"
  if printf '%s' "$health" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["status"] == "ok"
assert d["helper"]["helper_available"] is True
assert d["actions_enabled"] is True
'; then
    pass "Lab Manager health" "helper available; actions enabled"
  else
    fail "Lab Manager health" "$health"
  fi

  local socket="${IOTLAB_SOCKET:-/run/iotlab/helper.sock}"
  [[ -S "$socket" ]] || fail "Helper socket" "missing: $socket"
  local mode group
  mode="$(stat -c '%a' "$socket")"
  group="$(stat -c '%G' "$socket")"
  [[ "$mode" == "660" && "$group" == "iotlab" ]] \
    || fail "Helper socket permissions" "mode=$mode group=$group (expected 660/iotlab)"
  pass "Helper socket" "$socket mode=$mode group=$group"

  if systemctl show iotlab-manager.service -p ExecStart | grep -q '127.0.0.1'; then
    pass "Manager binding" "127.0.0.1"
  else
    fail "Manager binding" "manager is not configured for localhost"
  fi
}

check_installation_assets() {
  local version
  version="$(tr -d '[:space:]' < "$DEST/current/VERSION")"
  pass "Installed version" "$version"

  local key="$DEST/var/secrets/week01_controller_ed25519"
  [[ -f "$key" ]] || fail "Student SSH key" "missing: $key"
  local key_meta
  key_meta="$(stat -c '%a %G' "$key")"
  [[ "$key_meta" == "640 iotlab-students" ]] \
    || fail "Student SSH key permissions" "$key_meta (expected 640 iotlab-students)"
  pass "Student SSH key permissions" "$key_meta"

  local evidence_meta
  evidence_meta="$(stat -c '%a %G' "$DEST/var/evidence")"
  [[ "$evidence_meta" == "770 iotlab" ]] \
    || fail "Evidence directory permissions" "$evidence_meta (expected 770 iotlab)"
  pass "Evidence directory permissions" "$evidence_meta"

  local desktop=/usr/share/applications/iotlab-manager.desktop
  [[ -f "$desktop" ]] || fail "Desktop launcher" "missing: $desktop"
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$desktop" \
      || fail "Desktop launcher" "desktop-file-validate failed"
  fi
  pass "Desktop launcher" "$desktop"

  if id "$STUDENT_USER" >/dev/null 2>&1; then
    if id -nG "$STUDENT_USER" | tr ' ' '\n' | grep -qx iotlab-students; then
      pass "Student group membership" "$STUDENT_USER in iotlab-students"
    else
      warn "Student group membership" "add with: usermod -aG iotlab-students $STUDENT_USER"
    fi
  else
    warn "Student group membership" "user $STUDENT_USER does not exist on this VM"
  fi
}

check_manager_catalog() {
  local labs
  labs="$(api_get /api/labs)"
  if printf '%s' "$labs" | python3 -c '
import json, sys
d = json.load(sys.stdin)
labs = d["labs"]
assert len(labs) == 18
assert sum(1 for item in labs if item["availability"] == "available") == 1
assert sum(1 for item in labs if item["module_type"] == "assessment") == 1
assert d["actions_enabled"] is True
'; then
    pass "Module catalog" "18 modules, 1 available, 1 assessment"
  else
    fail "Module catalog" "unexpected /api/labs payload"
  fi

  if api_get /api/labs/week01/instructions | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["format"] == "markdown"
assert "Week 01" in d["content"]
'; then
    pass "Instructions endpoint" "Week 1 README available"
  else
    fail "Instructions endpoint" "could not read Week 1 instructions"
  fi
}

week1_start() {
  local start
  start="$(api_post /api/labs/week01/actions/start)" \
    || fail "Manager start" "POST start failed"
  if printf '%s' "$start" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["status"] == "ok"
assert d["lab"] == "week01"
'; then
    pass "Manager start" "Week 1 started"
  else
    fail "Manager start" "$start"
  fi

  local status
  status="$(api_get /api/labs/week01/status)" \
    || fail "Manager status" "status endpoint failed"
  if printf '%s' "$status" | python3 -c '
import json, sys
d = json.load(sys.stdin)
services = {item["service"] for item in d["containers"]}
assert d["healthy"] is True
assert services == {"camera", "gateway", "controller"}
assert d["published_port_count"] == 0
assert {item["port"] for item in d["expected_services"]} == {22, 1883, 8080, 8554}
'; then
    pass "Container health" "all three healthy; no published ports"
    pass "Expected services" "22, 1883, 8080, 8554"
  else
    fail "Container health" "$status"
  fi

  if docker ps -q --filter label=iotlab.lab=week01 | xargs -r docker inspect \
    --format '{{json .HostConfig.PortBindings}}' | grep -vq '^{}$\|null'; then
    fail "External port exposure" "a Week 1 container has a host port binding"
  fi
  pass "External port exposure" "no host bindings"
}

week1_checks() {
  local camera gateway_iot controller gateway_mgmt
  camera="$(container_ip iotlab_w01_camera iotlab_w01_iot)"
  gateway_iot="$(container_ip iotlab_w01_gateway iotlab_w01_iot)"
  controller="$(container_ip iotlab_w01_controller iotlab_w01_mgmt)"
  gateway_mgmt="$(container_ip iotlab_w01_gateway iotlab_w01_mgmt)"
  [[ -n "$camera" && -n "$gateway_iot" && -n "$controller" && -n "$gateway_mgmt" ]] \
    || fail "Container addressing" "could not resolve lab IPs"

  local camera_body
  camera_body="$(docker run --rm --network iotlab_w01_iot alpine:3.20.3 \
    wget -qO- http://camera:8080/status)"
  grep -q 'VC-100' <<< "$camera_body" \
    || fail "Camera HTTP" "unexpected camera status response"
  pass "Camera HTTP" "virtual camera responded"

  docker exec iotlab_w01_gateway mosquitto_pub -h 127.0.0.1 \
    -t iotlab/acceptance -m ok >/dev/null
  pass "MQTT publish" "gateway accepted a message"

  local scan_iot scan_mgmt
  scan_iot="$(docker run --rm --network iotlab_w01_iot \
    instrumentisto/nmap:7.95-r0 -sT -Pn -n -p 22,1883,8080,8554 -oG - \
    "$camera" "$gateway_iot")"
  assert_nmap_open "Nmap camera HTTP" "$camera" 8080 "$scan_iot"
  assert_nmap_open "Nmap camera RTSP" "$camera" 8554 "$scan_iot"
  assert_nmap_open "Nmap MQTT (IoT)" "$gateway_iot" 1883 "$scan_iot"

  scan_mgmt="$(docker run --rm --network iotlab_w01_mgmt \
    instrumentisto/nmap:7.95-r0 -sT -Pn -n -p 22,1883,8080,8554 -oG - \
    "$controller" "$gateway_mgmt")"
  assert_nmap_open "Nmap controller SSH" "$controller" 22 "$scan_mgmt"
  assert_nmap_open "Nmap MQTT (management)" "$gateway_mgmt" 1883 "$scan_mgmt"

  local version ssh_image whoami
  version="$(tr -d '[:space:]' < "$DEST/current/VERSION")"
  ssh_image="iotlab/test-ssh-client:${version}"
  if ! docker image inspect "$ssh_image" >/dev/null 2>&1; then
    fail "SSH authentication" "missing offline tool image $ssh_image"
  fi
  whoami="$(docker run --rm --network iotlab_w01_mgmt \
    -v "$DEST/var/secrets/week01_controller_ed25519:/key:ro" \
    "$ssh_image" -i /key -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
    labuser@controller whoami)"
  grep -qx 'labuser' <<< "$whoami" \
    || fail "SSH authentication" "unexpected identity: $whoami"
  pass "SSH authentication" "labuser key login succeeded"

  local evidence
  evidence="$(api_get /api/labs/week01/evidence)"
  if printf '%s' "$evidence" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["runtime_available"] is True
names = {item["name"] for item in d["runtime_files"]}
assert "camera-events.log" in names
'; then
    pass "Evidence listing" "camera-events.log present"
  else
    fail "Evidence listing" "runtime evidence unavailable"
  fi

  if api_get /api/labs/week01/evidence/camera-events.log | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["source"] == "runtime"
assert "startup" in d["content"]
'; then
    pass "Evidence reading" "camera event log readable"
  else
    fail "Evidence reading" "could not read camera event log"
  fi
}

week1_stop_reset() {
  local stop status
  stop="$(api_post /api/labs/week01/actions/stop)" \
    || fail "Manager stop" "POST stop failed"
  if printf '%s' "$stop" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["status"] == "ok"
'; then
    pass "Manager stop" "Week 1 stopped"
  else
    fail "Manager stop" "$stop"
  fi

  status="$(api_get /api/labs/week01/status)"
  if printf '%s' "$status" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["containers"] == []
'; then
    pass "Stopped status" "no containers running"
  else
    fail "Stopped status" "$status"
  fi

  docker run --rm -v iotlab_w01_camera_state:/state alpine:3.20.3 \
    sh -c 'echo acceptance-state-marker > /state/acceptance-reset-marker'
  docker run --rm -v iotlab_w01_evidence:/evidence alpine:3.20.3 \
    sh -c 'echo acceptance-evidence-marker > /evidence/acceptance-reset-evidence'

  local reset
  reset="$(api_post /api/labs/week01/actions/reset)" \
    || fail "Manager reset" "POST reset failed"
  if printf '%s' "$reset" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["status"] == "ok"
'; then
    pass "Manager reset" "Week 1 reset"
  else
    fail "Manager reset" "$reset"
  fi

  status="$(api_get /api/labs/week01/status)"
  if printf '%s' "$status" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["healthy"] is True
assert d["published_port_count"] == 0
'; then
    pass "Reset health" "healthy; no published ports"
  else
    fail "Reset health" "$status"
  fi

  if docker run --rm -v iotlab_w01_camera_state:/state alpine:3.20.3 \
    test ! -f /state/acceptance-reset-marker; then
    pass "Reset state" "camera state marker removed"
  else
    fail "Reset state" "camera state marker survived reset"
  fi

  if docker run --rm -v iotlab_w01_evidence:/evidence alpine:3.20.3 \
    test -f /evidence/acceptance-reset-evidence; then
    pass "Evidence preservation" "evidence marker survived reset"
  else
    fail "Evidence preservation" "evidence marker was removed"
  fi

  if api_get /api/labs/week01/evidence/acceptance-reset-evidence | \
    python3 -c '
import json, sys
d = json.load(sys.stdin)
assert "acceptance-evidence-marker" in d["content"]
'; then
    pass "Evidence after reset" "marker readable through the manager"
  else
    fail "Evidence after reset" "marker not readable"
  fi

  api_post /api/labs/week01/actions/stop >/dev/null \
    || fail "Final stop" "could not stop Week 1"
  pass "Final stop" "laboratory left stopped"
}

main() {
  parse_args "$@"
  check_host
  REPORT="${REPORT:-/var/log/iotlab-ubuntu-acceptance-$(date -u +%Y%m%dT%H%M%SZ).md}"
  mkdir -p "$(dirname "$REPORT")"
  exec > >(tee -a "$REPORT") 2>&1

  printf '# HAU IoT Security Lab - Ubuntu 24.04 Acceptance\n\n'
  printf -- '- Started: %s\n' "$(timestamp)"
  printf -- '- Host: %s\n' "$(uname -a)"
  printf -- '- Destination: %s\n' "$DEST"

  section "Host"
  pass "Operating system" "${OS_PRETTY} $(uname -m)"
  pass "Docker Compose" "$COMPOSE_VERSION"

  section "Installation"
  install_under_test

  section "Services and manager"
  check_services
  check_installation_assets
  check_manager_catalog

  section "Week 1 via Lab Manager"
  week1_start
  week1_checks
  week1_stop_reset

  printf '\n### Result\n\n'
  printf '**PASSED** with %s passing check(s) and %s warning(s).\n' \
    "$PASS_COUNT" "$WARN_COUNT"
  printf -- '- Finished: %s\n' "$(timestamp)"
  printf -- '- Report: %s\n' "$REPORT"
  exit 0
}

main "$@"
