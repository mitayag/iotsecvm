#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage: scripts/gen-lab-keys.sh <week>

Generates a per-lab Ed25519 key pair under var/secrets/ if one does not exist.
The private key is chmod 600 and must never be committed or shared.
EOF
}

main() {
  local week="${1:-}"
  [[ -n "$week" ]] || { usage; exit 1; }
  load_lab "$week"
  require_command ssh-keygen

  local secrets_dir="$ROOT/var/secrets"
  local key_file="$secrets_dir/${LAB_ID}_controller_ed25519"
  local pub_file="${key_file}.pub"
  local authorized_file="$secrets_dir/${LAB_ID}_controller_authorized_keys"

  mkdir -p "$secrets_dir"
  chmod 0700 "$secrets_dir"

  if [[ ! -f "$key_file" ]]; then
    ssh-keygen -q -t ed25519 -N "" -C "iotlab-${LAB_ID}" -f "$key_file"
    chmod 0600 "$key_file"
    chmod 0644 "$pub_file"
    log "generated lab key: $key_file"
  else
    log "reusing existing lab key: $key_file"
  fi

  [[ -f "$pub_file" ]] || die "public key missing: $pub_file"
  cp "$pub_file" "$authorized_file"
  chmod 0644 "$authorized_file"
  log "authorized keys file ready: $authorized_file"
}

main "$@"
