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
  local key_group="${IOTLAB_KEY_GROUP:-}"

  mkdir -p "$secrets_dir"

  if [[ ! -f "$key_file" ]]; then
    ssh-keygen -q -t ed25519 -N "" -C "iotlab-${LAB_ID}" -f "$key_file"
    log "generated lab key: $key_file"
  else
    log "reusing existing lab key: $key_file"
  fi

  [[ -f "$pub_file" ]] || die "public key missing: $pub_file"
  cp "$pub_file" "$authorized_file"

  if [[ -n "$key_group" ]]; then
    getent group "$key_group" >/dev/null 2>&1 \
      || die "key group does not exist: $key_group"
    chgrp "$key_group" "$secrets_dir" "$key_file" "$pub_file" "$authorized_file"
    chmod 0750 "$secrets_dir"
    chmod 0640 "$key_file"
  else
    chmod 0700 "$secrets_dir"
    chmod 0600 "$key_file"
  fi
  chmod 0644 "$pub_file" "$authorized_file"
  log "authorized keys file ready: $authorized_file"
}

main "$@"
