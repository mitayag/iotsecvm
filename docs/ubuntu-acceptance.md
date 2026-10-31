# Native Ubuntu 24.04 acceptance test

This procedure is for a **disposable** Ubuntu 24.04 LTS x86-64 VM. Do not run it
on a workstation or a VM holding data you need to keep.

## Preconditions

- Ubuntu 24.04 LTS, x86-64, minimum 4 GB RAM and 20 GB free disk.
- Docker Engine and Compose v2 installed and working.
- Python 3.12 with `python3-venv`.
- `curl`, `systemd`, `sha256sum`, `tar`, `stat`.
- The offline bundle copied to the VM, for example
  `iotlab-0.2.0-offline-x86_64.tar.gz`.
- A student login account for group-membership checks (default `student`).
- Root/sudo access for installation and systemd.

The VM does not need internet access. The bundle contains the lab images, Nmap,
Alpine evidence tooling, the SSH test client and Linux x86-64 wheels.

## Run

The recommended path is a fresh install from the bundle:

```bash
sha256sum iotlab-0.2.0-offline-x86_64.tar.gz
sudo scripts/acceptance-ubuntu.sh \
  --bundle iotlab-0.2.0-offline-x86_64.tar.gz \
  --sha256 <printed-or-published-sha256> \
  --dest /opt/iotlab \
  --student-user student
```

To test an existing installation without reinstalling:

```bash
sudo scripts/acceptance-ubuntu.sh --skip-install --student-user student
```

The script refuses to run on any platform other than Ubuntu 24.04 x86-64, and
refuses to run without root.

## What it verifies

### Host and installation

- Ubuntu version, architecture, Docker daemon and Compose v2.
- Bundle SHA256 and internal `SHA256SUMS`.
- Offline image load and wheel installation.
- Immutable release layout and installed version.

### Services and permissions

- `iotlab-helper.service` and `iotlab-manager.service` active.
- Lab Manager health reports helper available and actions enabled.
- Helper socket exists at `/run/iotlab/helper.sock` with mode `0660`, group
  `iotlab`.
- Manager configured for `127.0.0.1`.
- SSH private key mode `0640`, group `iotlab-students`.
- Evidence directory mode `0770`, group `iotlab`.
- Desktop launcher installed and valid when `desktop-file-validate` is present.
- Student account in `iotlab-students` (warning if not provisioned).

### Lab Manager and Week 1

- Catalog: 18 modules, 1 available, 1 assessment.
- Week 1 instructions.
- Manager starts Week 1.
- Containers healthy; expected services 22, 1883, 8080 and 8554.
- Zero externally published ports.
- Camera HTTP status returns the `VC-100` device.
- MQTT publish succeeds.
- Nmap finds camera 8080/8554, gateway 1883 and controller 22.
- SSH key login returns `labuser`.
- Evidence listing and reading include `camera-events.log`.
- Manager stops the lab; no containers remain.
- Reset removes camera state and preserves the evidence marker.
- Reset restarts a healthy lab with no published ports.
- Final stop leaves the lab stopped.

## Report

The script writes a Markdown report to:

```text
/var/log/iotlab-ubuntu-acceptance-<UTC timestamp>.md
```

It exits non-zero on the first failure and records the failing check. Attach the
report and the bundle SHA256 to the acceptance record.

## Pass criteria

- Every check in the report is `PASS`; warnings must be explained in the
  instructor sign-off.
- No container has a host port binding.
- Evidence survives reset.
- The native report contains a real UTC timestamp and the Ubuntu host details.
- Do not mark native acceptance complete from macOS or CI emulation.

## After the test

Archive the report, bundle hash, image manifest and CI run identifiers. Uninstall
or discard the disposable VM. Do not add the test account to `iotlab-students` on
production VMs without an instructor decision.

## Current status

Prepared and syntax/guard checked on 2026-10-31. **Not executed on native
Ubuntu 24.04 yet.** The macOS validation and Linux amd64 emulation results are
recorded in `ACCEPTANCE-STAGE2.md` and are not a substitute for this run.
