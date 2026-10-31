# Troubleshooting

## Docker is unavailable

```bash
docker info
docker compose version
```

The scripts require Docker Engine and Compose v2. On Ubuntu, ensure the service
is running and the operator can access Docker through an approved mechanism.

## Network ownership error

`networks.sh` refuses to reuse a network with a different `iotlab.lab` label.

```bash
docker network inspect iotlab_w01_iot
```

Remove stale networks only after the lab containers are gone:

```bash
scripts/lab-stop.sh week01
scripts/networks.sh remove week01
scripts/networks.sh ensure week01
```

## Containers are unhealthy

```bash
scripts/lab-status.sh week01
docker compose -p iotlab-week01 -f labs/week01/docker-compose.yml logs --no-color
```

Common causes: images were not built, the per-lab key is missing, or a state
volume was created with unexpected ownership.

## Lab Manager reports read-only mode

```bash
systemctl status iotlab-helper.service iotlab-manager.service
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool
```

Check the helper socket:

```bash
ls -l /run/iotlab/helper.sock
journalctl -u iotlab-helper.service -n 50 --no-pager
```

Expected socket ownership is `root:iotlab` with mode `0660`. The manager unit
must run with group `iotlab` and set `IOTLAB_HELPER_SOCKET`.

## Lab Manager operation fails with 409 busy

Only one helper operation may run at a time. Wait for the current start, stop or
reset to finish, then retry. Check `iotlab-helper` logs for a stuck script.

## SSH login fails

```bash
scripts/gen-lab-keys.sh week01
scripts/lab-reset.sh week01 --yes
```

The controller authorises the public key in
`var/secrets/week01_controller_authorized_keys`. The private key is
`var/secrets/week01_controller_ed25519`. Password authentication is disabled.

On a production install, add the student account to the `iotlab` group and log
in again:

```bash
sudo usermod -aG iotlab-students student
```

## Reset reports evidence preservation

The evidence volume is intentionally kept. Export it before instructor archival:

```bash
scripts/lab-evidence.sh export week01 /tmp/week01-evidence
```

## Ports appear closed in Nmap

Scan from a container attached to the correct lab network. Running Nmap on the
host will not see internal lab services because nothing is published.

```bash
docker run --rm --network iotlab_w01_iot instrumentisto/nmap:7.95-r0 \
  -sT -Pn -n -p 22,1883,8080,8554 10.231.1.0/24
```

## Deployment verification fails

Inspect the history and roll back:

```bash
sudo tail -n 20 /opt/iotlab/var/deploy/history.log
sudo /opt/iotlab/current/scripts/rollback.sh --dest /opt/iotlab
```

## Python dependency errors

Recreate the development environment:

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -r tests/requirements-dev.txt
```
