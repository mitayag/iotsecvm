# Deployment and rollback

The supported target is a self-contained Ubuntu 24.04 LTS x86-64 VM operating
without internet access. Deployment never requires Kali Linux, Proxmox or an AI
harness.

## Release layout

```text
/opt/iotlab/
├── current -> releases/0.1.0
├── releases/0.1.0/       immutable application tree
├── releases/0.1.1/
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
- Python 3.12, OpenSSH client tools,
- an `iotlab` system user for the manager service.

```bash
tar -xf iotlab-0.1.0-offline-x86_64.tar.gz
sudo iotlab-0.1.0/scripts/install.sh \
  --offline-images iotlab-0.1.0/images/iotlab-images.tar \
  --wheelhouse iotlab-0.1.0/wheels \
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
7. installs and starts `iotlab-manager.service` on `127.0.0.1:8080`.

The service does not join the Docker group and has no Docker socket. Mutating
web actions remain disabled (`IOTLAB_ALLOW_MUTATIONS=0`).

## Update from a new bundle

```bash
sudo scripts/update.sh --bundle /media/iotlab-0.1.1-offline-x86_64.tar.gz
```

`update.sh` verifies `SHA256SUMS`, loads the new images, deploys the new release,
installs wheels and verifies the result. Evidence volumes and keys are retained.
If verification fails, `deploy.sh` switches `current` back to the previous
release automatically.

## Manual rollback

```bash
sudo /opt/iotlab/current/scripts/rollback.sh --dest /opt/iotlab
```

Or select a specific release:

```bash
sudo /opt/iotlab/current/scripts/rollback.sh 0.1.0 --dest /opt/iotlab
```

Rollback switches only the application tree. Running labs should be stopped and
restarted after a rollback:

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

The Stage 1 test suite performs a real two-release deploy and rollback in a
temporary directory, verifies the symlink target, checks deployment history and
confirms that shared evidence survives. See `tests/test_deploy.py` and
`ACCEPTANCE.md`.

## Restrictions

- Do not push releases to GitHub without explicit approval.
- Do not publish vulnerable services on host interfaces.
- Do not commit generated keys, bundles or evidence.
- Do not add the manager user to the Docker group.
