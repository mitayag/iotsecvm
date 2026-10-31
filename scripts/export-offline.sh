#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/export-offline.sh [--platform linux/amd64] [--no-wheels] [--skip-build]

Builds all implemented lab images and creates an offline bundle containing:

  iotlab-VERSION/        source tree
  images/                docker save archive and image manifest
  wheels/                Linux x86-64 Python wheels for the lab manager
  SHA256SUMS

The default platform is linux/amd64, the Stage 1 target. The bundle can be
copied to the student VM and installed with update.sh.
EOF
}

hash_files() {
  local dir="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$dir" && find . -type f ! -name SHA256SUMS ! -name '.DS_Store' \
      -exec sha256sum {} +)
  else
    (cd "$dir" && find . -type f ! -name SHA256SUMS ! -name '.DS_Store' \
      -exec shasum -a 256 {} +)
  fi
}

SUPPORT_IMAGES=(
  "alpine:3.20.3"
  "instrumentisto/nmap:7.95-r0"
)

pull_platform_image() {
  local image="$1" platform="$2" arch="$3" name digest
  name="${image%:*}"
  digest="$(docker manifest inspect -v "$image" | python3 -c "
import json, sys
items = json.load(sys.stdin)
if isinstance(items, dict):
    items = [items]
match = [
    item for item in items
    if item.get('Descriptor', {}).get('platform', {}).get('os') == 'linux'
    and item.get('Descriptor', {}).get('platform', {}).get('architecture') == '$arch'
]
if not match:
    raise SystemExit('no $arch manifest for $image')
print(match[0]['Descriptor']['digest'])
")"
  docker pull --quiet "${name}@${digest}" >/dev/null
  docker tag "${name}@${digest}" "$image"
}

main() {
  local with_wheels=1
  local skip_build=0
  local platform="linux/amd64"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform) platform="${2:-}"; shift ;;
      --no-wheels) with_wheels=0 ;;
      --skip-build) skip_build=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "unknown option: $1" ;;
    esac
    shift
  done

  require_docker
  require_command tar

  local arch
  case "$platform" in
    linux/amd64) arch="x86_64" ;;
    linux/arm64) arch="aarch64" ;;
    *) die "unsupported platform: $platform (use linux/amd64 or linux/arm64)" ;;
  esac
  export DOCKER_DEFAULT_PLATFORM="$platform"

  local bundle_name="iotlab-${IOTLAB_VERSION}-offline-${arch}.tar.gz"
  local staging
  staging="$(mktemp -d "${TMPDIR:-/tmp}/iotlab-export.XXXXXX")"
  trap 'rm -rf "${staging:-}"' EXIT

  mkdir -p "$staging/images" "$staging/wheels" "$staging/iotlab-$IOTLAB_VERSION"

  if (( skip_build == 0 )); then
    for manifest in "$ROOT"/labs/week*/lab.yaml; do
      local lab_dir
      lab_dir="$(dirname "$manifest")"
      [[ -f "$lab_dir/docker-compose.yml" ]] || continue
      "$ROOT/scripts/lab-build.sh" "$(basename "$lab_dir")"
    done
  fi

  log "preparing offline support images"
  local support_image
  for support_image in "${SUPPORT_IMAGES[@]}"; do
    pull_platform_image "$support_image" "$platform" "${platform##*/}"
  done
  local ssh_client_image="iotlab/test-ssh-client:${IOTLAB_VERSION}"
  docker build --quiet --platform "$platform" \
    -t "$ssh_client_image" "$ROOT/tests/images/ssh-client" >/dev/null

  log "collecting image references"
  local images
  images="$(
    {
      for manifest in "$ROOT"/labs/week*/lab.yaml; do
        local lab_dir
        lab_dir="$(dirname "$manifest")"
        [[ -f "$lab_dir/docker-compose.yml" ]] || continue
        docker compose -f "$lab_dir/docker-compose.yml" config --images
      done
      printf '%s\n' "${SUPPORT_IMAGES[@]}"
      printf '%s\n' "$ssh_client_image"
    } | sort -u
  )"
  [[ -n "$images" ]] || die "no lab images found to export"

  while IFS= read -r image; do
    [[ -n "$image" ]] || continue
    local actual
    actual="$(docker image inspect -f '{{.Os}}/{{.Architecture}}' "$image")"
    [[ "$actual" == "$platform" ]] \
      || die "image $image is $actual, expected $platform; rebuild it for $platform"
  done <<< "$images"

  printf '%s\n' "$images" > "$staging/images/image-list.txt"
  # shellcheck disable=SC2086
  docker save -o "$staging/images/iotlab-images.tar" $images

  log "recording image provenance"
  : > "$staging/images/manifest.txt"
  while IFS= read -r image; do
    [[ -n "$image" ]] || continue
    printf '%s\n' "$image" >> "$staging/images/manifest.txt"
    docker image inspect -f '  id={{.Id}} digests={{join .RepoDigests ","}}' \
      "$image" >> "$staging/images/manifest.txt"
  done <<< "$images"

  log "copying source tree"
  tar -C "$ROOT" \
    --exclude=.git \
    --exclude=.venv \
    --exclude=var \
    --exclude=dist \
    --exclude=__pycache__ \
    --exclude=.pytest_cache \
    -cf - . | tar -C "$staging/iotlab-$IOTLAB_VERSION" -xf -

  if (( with_wheels == 1 )); then
    log "downloading Linux x86-64 Python wheels"
    docker run --rm --platform "$platform" \
      -v "$ROOT/backend/requirements.txt:/requirements.txt:ro" \
      -v "$staging/wheels:/wheels" \
      python:3.12.8-slim-bookworm \
      pip download --disable-pip-version-check --only-binary=:all: \
      --dest /wheels -r /requirements.txt
  else
    warn "Python wheels omitted; offline manager install will not be possible"
  fi

  log "writing checksums"
  hash_files "$staging" > "$staging/SHA256SUMS"

  mkdir -p "$ROOT/dist"
  log "creating bundle"
  tar -C "$staging" -czf "$ROOT/dist/$bundle_name" \
    "iotlab-$IOTLAB_VERSION" images wheels SHA256SUMS

  log "offline bundle ready: $ROOT/dist/$bundle_name"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$ROOT/dist/$bundle_name"
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$ROOT/dist/$bundle_name"
  fi
}

main "$@"
