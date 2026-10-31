#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/update.sh --bundle FILE [options]

  --bundle FILE   Offline bundle produced by scripts/export-offline.sh
  --dest DIR      Deployment home (default: IOTLAB_HOME or /opt/iotlab)
  --skip-verify   Skip post-deployment verification

The bundle is verified with SHA256SUMS, images are loaded, the new release is
deployed, Python dependencies are installed from the bundled wheelhouse, and
the previous release remains available for rollback.
EOF
}

sha256_check() {
  local dir="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$dir" && sha256sum -c SHA256SUMS)
  else
    (cd "$dir" && shasum -a 256 -c SHA256SUMS)
  fi
}

main() {
  local bundle=""
  local dest="${IOTLAB_HOME:-/opt/iotlab}"
  local skip_verify=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --bundle) bundle="${2:-}"; shift ;;
      --dest) dest="${2:-}"; shift ;;
      --skip-verify) skip_verify=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  [[ -n "$bundle" && -f "$bundle" ]] || die "offline bundle not found"
  require_docker
  require_command tar
  require_command python3

  local staging
  staging="$(mktemp -d "${TMPDIR:-/tmp}/iotlab-update.XXXXXX")"
  trap 'rm -rf "${staging:-}"' EXIT

  log "extracting bundle"
  tar -C "$staging" -xf "$bundle"
  if [[ -f "$staging/SHA256SUMS" ]]; then
    log "verifying bundle checksums"
    sha256_check "$staging"
  else
    warn "bundle has no SHA256SUMS; continuing without integrity verification"
  fi

  local source_dir
  source_dir="$(find "$staging" -maxdepth 2 -type f -name VERSION -print | head -n 1 | xargs dirname)"
  [[ -n "$source_dir" && -f "$source_dir/VERSION" ]] || die "release source not found in bundle"
  local version
  version="$(tr -d '[:space:]' < "$source_dir/VERSION")"

  local deploy_args=(
    --source "$source_dir"
    --version "$version"
    --dest "$dest"
    --skip-verify
  )
  if [[ -f "$staging/images/iotlab-images.tar" ]]; then
    deploy_args+=(--offline-images "$staging/images/iotlab-images.tar")
  fi

  local previous=""
  if [[ -f "$dest/var/deploy/previous" ]]; then
    previous="$(tr -d '[:space:]' < "$dest/var/deploy/previous")"
  fi

  "$ROOT/scripts/deploy.sh" "${deploy_args[@]}"

  if [[ ! -x "$dest/venv/bin/python" ]]; then
    log "creating shared Python environment"
    python3 -m venv "$dest/venv"
  fi

  if [[ -d "$staging/wheels" ]] && compgen -G "$staging/wheels/*" >/dev/null; then
    log "installing backend dependencies from offline wheelhouse"
    if ! "$dest/venv/bin/pip" install --no-index --find-links "$staging/wheels" \
      -r "$dest/current/backend/requirements.txt"; then
      warn "wheel installation failed"
      if [[ -n "$previous" ]]; then
        "$dest/current/scripts/rollback.sh" --dest "$dest" "$previous" || true
      fi
      exit 1
    fi
  else
    warn "bundle has no Python wheels; manager dependencies were not installed"
  fi

  if (( skip_verify == 0 )); then
    if ! "$dest/current/scripts/verify.sh"; then
      warn "verification failed after dependency installation"
      if [[ -n "$previous" ]]; then
        "$dest/current/scripts/rollback.sh" --dest "$dest" "$previous" || true
      fi
      exit 1
    fi
  fi

  log "update complete: $dest/current -> $version"
  log "restart installed services: systemctl restart iotlab-helper iotlab-manager"
}

main "$@"
