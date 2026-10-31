#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/install.sh [options]

  --dest DIR             Installation home (default: /opt/iotlab)
  --offline-images FILE  docker save archive to load during install
  --wheelhouse DIR       Directory containing pre-downloaded Python wheels
  --no-systemd           Do not install or start the lab manager service
  --skip-verify          Skip the post-install verification
  --yes                  Non-interactive confirmation

Ubuntu 24.04 LTS x86-64 is the supported target. Run as root for the default
destination and systemd integration.
EOF
}

main() {
  local dest="${IOTLAB_HOME:-/opt/iotlab}"
  local offline_images=""
  local wheelhouse=""
  local use_systemd=1
  local skip_verify=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dest) dest="${2:-}"; shift ;;
      --offline-images) offline_images="${2:-}"; shift ;;
      --wheelhouse) wheelhouse="${2:-}"; shift ;;
      --no-systemd) use_systemd=0 ;;
      --skip-verify) skip_verify=1 ;;
      --yes|-y) ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  require_docker
  require_command python3
  require_command ssh-keygen

  if [[ "$(uname -s)" != "Linux" ]]; then
    warn "target platform is Ubuntu 24.04 LTS; continuing on $(uname -s)"
  fi

  if ! mkdir -p "$dest" 2>/dev/null; then
    die "cannot create $dest; rerun with sudo or choose --dest"
  fi
  [[ -w "$dest" ]] || die "$dest is not writable; rerun with sudo"

  mkdir -p "$dest/releases" "$dest/var/evidence" "$dest/var/secrets" \
    "$dest/var/backups" "$dest/var/deploy"

  log "installing release $IOTLAB_VERSION into $dest"
  local deploy_args=(
    --source "$ROOT"
    --version "$IOTLAB_VERSION"
    --dest "$dest"
    --skip-verify
  )
  if [[ -n "$offline_images" ]]; then
    deploy_args+=(--offline-images "$offline_images")
  fi
  if [[ -d "$dest/current" || -e "$dest/releases/$IOTLAB_VERSION" ]]; then
    deploy_args+=(--force)
  fi
  "$ROOT/scripts/deploy.sh" "${deploy_args[@]}"

  log "preparing Python environment"
  if [[ ! -x "$dest/venv/bin/python" ]]; then
    python3 -m venv "$dest/venv"
  fi
  if [[ -n "$wheelhouse" ]]; then
    [[ -d "$wheelhouse" ]] || die "wheelhouse not found: $wheelhouse"
    "$dest/venv/bin/pip" install --no-index --find-links "$wheelhouse" \
      -r "$dest/current/backend/requirements.txt"
  else
    "$dest/venv/bin/pip" install --disable-pip-version-check \
      -r "$dest/current/backend/requirements.txt"
  fi

  log "generating per-lab SSH keys (private keys remain on this host)"
  "$dest/current/scripts/gen-lab-keys.sh" week01

  if (( skip_verify == 0 )); then
    "$dest/current/scripts/verify.sh"
  fi

  if (( use_systemd == 1 )); then
    if [[ "$(uname -s)" != "Linux" ]]; then
      warn "systemd skipped outside Linux"
    elif [[ "$(id -u)" != "0" ]]; then
      warn "systemd skipped because the installer is not running as root"
    else
      if ! getent group iotlab >/dev/null 2>&1; then
        groupadd --system iotlab
      fi
      if ! id -u iotlab >/dev/null 2>&1; then
        useradd --system --gid iotlab --home-dir "$dest" \
          --shell /usr/sbin/nologin iotlab
      fi
      sed "s|/opt/iotlab|$dest|g" \
        "$dest/current/deploy/iotlab-manager.service" \
        > /etc/systemd/system/iotlab-manager.service
      chmod 0644 /etc/systemd/system/iotlab-manager.service
      systemctl daemon-reload
      systemctl enable --now iotlab-manager.service
      log "lab manager service started on 127.0.0.1:8080"
    fi
  fi

  log "installation complete: $dest/current"
  log "start Week 1 with: $dest/current/scripts/lab-start.sh week01"
}

main "$@"
