#!/bin/sh
set -eu

mkdir -p /run/sshd /home/labuser/.ssh /evidence
chmod 0755 /run/sshd
chown -R labuser:labuser /home/labuser/.ssh
chmod 0700 /home/labuser/.ssh

if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
  ssh-keygen -A
fi

if [ -s /run/secrets/controller_authorized_keys ]; then
  install -m 0600 -o labuser -g labuser \
    /run/secrets/controller_authorized_keys \
    /home/labuser/.ssh/authorized_keys
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) controller ready with student key" >> /evidence/controller-startup.log
else
  echo "WARNING: no authorized key supplied; SSH logins will fail" >&2
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) controller started without a student key" >> /evidence/controller-startup.log
fi

exec /usr/sbin/sshd -D -e
