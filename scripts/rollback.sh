#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/rollback.sh [version] [--dest DIR]

Switches DEST/current to a previous release. Without a version argument, the
value in DEST/var/deploy/previous is used.
EOF
}

main() {
  local version=""
  local dest="${IOTLAB_HOME:-/opt/iotlab}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dest) dest="${2:-}"; shift ;;
      -h|--help) usage; exit 0 ;;
      -*) die "unknown option: $1" ;;
      *) version="$1" ;;
    esac
    shift
  done

  [[ -d "$dest/releases" ]] || die "no releases directory at $dest/releases"
  [[ -L "$dest/current" ]] || die "no current release symlink at $dest/current"

  if [[ -z "$version" ]]; then
    [[ -f "$dest/var/deploy/previous" ]] \
      || die "no previous release recorded; specify a version"
    version="$(tr -d '[:space:]' < "$dest/var/deploy/previous")"
  fi

  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]] \
    || die "invalid version: $version"
  [[ -d "$dest/releases/$version" ]] || die "release not found: $version"

  local current
  current="$(basename "$(readlink "$dest/current")")"
  [[ "$current" != "$version" ]] || die "$version is already current"

  ln -sfn "$dest/releases/$version" "$dest/current"
  printf '%s rollback %s -> %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$current" "$version" \
    >> "$dest/var/deploy/history.log"
  printf '%s\n' "$current" > "$dest/var/deploy/previous"
  log "rolled back: $current -> $version"
}

main "$@"
