#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/deploy.sh [options]

  --source DIR          Source tree to install (default: repository root)
  --version VERSION     Release version (default: VERSION file)
  --dest DIR            Deployment home (default: IOTLAB_HOME or /opt/iotlab)
  --offline-images FILE Load a docker save archive before switching
  --skip-verify         Skip the post-switch verification step
  --force               Replace an existing release directory

Layout:
  DEST/releases/VERSION/   immutable release
  DEST/current -> releases/VERSION
  DEST/var/                shared evidence, secrets, backups and deploy history

The previous release is recorded in DEST/var/deploy/previous for rollback.
EOF
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

switch_current() {
  local dest="$1" version="$2"
  ln -sfn "$dest/releases/$version" "$dest/current"
}

verify_release() {
  local dest="$1"
  "$dest/current/scripts/verify.sh" --quick
}

main() {
  local source="$ROOT"
  local version="$IOTLAB_VERSION"
  local dest="${IOTLAB_HOME:-/opt/iotlab}"
  local offline_images=""
  local skip_verify=0
  local force=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --source) source="${2:-}"; shift ;;
      --version) version="${2:-}"; shift ;;
      --dest) dest="${2:-}"; shift ;;
      --offline-images) offline_images="${2:-}"; shift ;;
      --skip-verify) skip_verify=1 ;;
      --force) force=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  [[ -n "$source" && -d "$source" ]] || die "source directory not found"
  [[ -n "$version" ]] || die "version is required"
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]] \
    || die "version must look like 1.2.3"
  [[ -n "$dest" ]] || die "destination is required"

  local release_dir="$dest/releases/$version"
  local previous=""
  mkdir -p "$dest/releases" "$dest/var/evidence" "$dest/var/secrets" \
    "$dest/var/backups" "$dest/var/deploy"

  if [[ -e "$release_dir" ]]; then
    if (( force == 1 )); then
      rm -rf "$release_dir"
    else
      die "release already exists: $release_dir (use --force to replace)"
    fi
  fi

  if [[ -L "$dest/current" ]]; then
    previous="$(basename "$(readlink "$dest/current")")"
  fi

  local staging
  staging="$(mktemp -d "$dest/.staging.XXXXXX")"
  trap 'rm -rf "${staging:-}"' EXIT

  log "preparing release $version from $source"
  tar -C "$source" \
    --exclude=.git \
    --exclude=.venv \
    --exclude=var \
    --exclude=dist \
    --exclude=__pycache__ \
    --exclude=.pytest_cache \
    -cf - . | tar -C "$staging" -xf -

  printf '%s\n' "$version" > "$staging/VERSION"
  ln -s ../../var "$staging/var"
  ln -s ../../venv "$staging/.venv"
  {
    printf 'version=%s\n' "$version"
    printf 'source=%s\n' "$source"
    printf 'deployed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'source_sha256=%s\n' "$(sha256_file "$staging/VERSION")"
  } > "$staging/.release"

  mv "$staging" "$release_dir"
  trap - EXIT

  if [[ -n "$offline_images" ]]; then
    [[ -f "$offline_images" ]] || die "offline image archive not found: $offline_images"
    log "loading container images from $offline_images"
    docker load -i "$offline_images"
  fi

  if [[ -n "$previous" && "$previous" != "$version" ]]; then
    printf '%s\n' "$previous" > "$dest/var/deploy/previous"
  fi

  log "switching current to $version"
  switch_current "$dest" "$version"
  printf '%s deployed %s previous=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$version" "${previous:-none}" \
    >> "$dest/var/deploy/history.log"

  if (( skip_verify == 0 )); then
    if ! verify_release "$dest"; then
      warn "verification failed; rolling back"
      if [[ -n "$previous" ]]; then
        switch_current "$dest" "$previous"
        printf '%s rollback %s -> %s reason=verify-failed\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$version" "$previous" \
          >> "$dest/var/deploy/history.log"
      fi
      die "deployment failed verification"
    fi
  fi

  log "deployment complete: $dest/current -> $release_dir"
}

main "$@"
