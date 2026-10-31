# Deployment and rollback

The supported target is a self-contained Ubuntu 24.04 LTS x86-64 VM operating
without internet access. Deployment never requires Kali Linux, Proxmox or an AI
harness.

## Release layout

```text
/opt/iotlab/
├── current -> releases/0.2.0
├── releases/0.2.0/       immutable application tree
├── releases/0.2.1/
├── venv/                 shared Python environment
└── var/
    ├── evidence/         host-side notes (named Docker volumes hold runtime evidence)
    ├── secrets/          generated lab SSH keys, never committed
    ├── backups/          administrator backups
    └── deploy/
        ├── history.log
        └── previous
```

`releases/<version>/var` links to the shared `var/` directory, so evidence,
keys and history survive release switches. Do not store secrets in releases.

## Build an offline bundle (connected development host)

```bash
make venv
scripts/verify.sh --integration
scripts/export-offline.sh
```

`export-offline.sh` defaults to `--platform linux/amd64` and names the bundle
`dist/iotlab-<version>-offline-x86_64.tar.gz`. Build and export an ARM64 bundle
with `--platform linux/arm64` only after completing the ARM64 checklist. The
bundle contains:

- the source tree,
- `images/iotlab-images.tar` from `docker save`,
- `images/manifest.txt` with image IDs and repository digests,
- Linux x86-64 Python wheels for the manager,
- `SHA256SUMS`.

Transfer the bundle and its printed SHA256 value to the student VM.

## Install on a fresh VM

Prerequisites, prepared by the instructor image or installation media:

- Ubuntu 24.04 LTS, x86-64,
- Docker Engine and Compose v2,
- Python 3.12 with `python3-venv`, OpenSSH client tools,
- an `iotlab` system user for the manager service (created by the installer),
- the student login account added to the `iotlab-students` group for SSH key access.

```bash
tar -xf iotlab-0.2.0-offline-x86_64.tar.gz
sudo iotlab-0.2.0/scripts/install.sh \
  --offline-images iotlab-0.2.0/images/iotlab-images.tar \
  --wheelhouse iotlab-0.2.0/wheels \
  --dest /opt/iotlab \
  --yes
```

The installer:

1. verifies the host dependencies,
2. loads pinned images,
3. deploys an immutable release and switches `current`,
4. creates the shared Python virtual environment from the wheelhouse,
5. generates per-student SSH keys under `var/secrets/`,
6. verifies the installation,
7. installs and starts `iotlab-helper.service` (root, Unix socket),
8. installs and starts `iotlab-manager.service` on `127.0.0.1:8080`,
9. installs `/usr/share/applications/iotlab-manager.desktop`,
10. sets evidence directory group write and secrets group read for `iotlab`.

The manager user does not join the Docker group and has no Docker socket. It
calls only the allowlisted helper. `/api/health` should report
`helper_available=true` and `actions_enabled=true`.

Add each student login to the key group:

```bash
sudo usermod -aG iotlab-students student
```

Log out and back in for the group change to take effect.

## Update from a new bundle

```bash
sudo scripts/update.sh --bundle /media/iotlab-0.2.1-offline-x86_64.tar.gz
```

`update.sh` verifies `SHA256SUMS`, loads the new images, deploys the new release,
installs wheels and verifies the result. Evidence volumes and keys are retained.
If verification fails, `deploy.sh` switches `current` back to the previous
release automatically. Restart the services after updating:

```bash
sudo systemctl restart iotlab-helper.service iotlab-manager.service
```

## Manual rollback

```bash
sudo /opt/iotlab/current/scripts/rollback.sh --dest /opt/iotlab
```

Or select a specific release:

```bash
sudo /opt/iotlab/current/scripts/rollback.sh 0.2.0 --dest /opt/iotlab
```

Rollback switches only the application tree. Restart the services and any
running lab after a rollback:

```bash
sudo systemctl restart iotlab-helper.service iotlab-manager.service
```

```bash
sudo /opt/iotlab/current/scripts/lab-stop.sh week01
sudo /opt/iotlab/current/scripts/lab-start.sh week01
```

## Backup before update

```bash
sudo tar -C /opt/iotlab -czf /var/backups/iotlab-var-$(date +%F).tar.gz var
```

Named Docker volumes can be exported with `scripts/lab-evidence.sh export` and
backed up with `docker run --rm -v iotlab_w01_evidence:/evidence ...`.

## Rollback test evidence

The test suite performs a real two-release deploy and rollback in a temporary
directory, verifies the symlink target, checks deployment history and confirms
that shared evidence survives. See `tests/test_deploy.py` and
`ACCEPTANCE-STAGE2.md`.

## Desktop integration

The installer copies `deploy/iotlab-manager.desktop` to
`/usr/share/applications/`. It opens `http://127.0.0.1:8080` with `xdg-open`.
The launcher is installed only on Linux when the installer runs as root. Use
`--no-desktop` to skip it.

## Permissions summary

| Path | Owner | Mode |
| --- | --- | --- |
| `/opt/iotlab/var` | root:iotlab | `0750` |
| `/opt/iotlab/var/evidence` | root:iotlab | `0770` |
| `/opt/iotlab/var/secrets` | root:iotlab-students | `0750` |
| SSH private key | root:iotlab-students | `0640` |
| helper socket | root:iotlab | `0660` |
| systemd units | root:root | `0644` |
| desktop launcher | root:root | `0644` |

## Restrictions

- Do not push releases to GitHub without explicit approval.
- Do not publish vulnerable services on host interfaces.
- Do not commit generated keys, bundles or evidence.
- Do not add the manager user to the Docker group.
- Add only trusted student accounts to the `iotlab-students` group; group
  membership grants read access to lab SSH keys.
