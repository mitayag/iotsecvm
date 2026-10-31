# Adding a weekly lab

Each week is a self-contained module described by `lab.yaml` and, when
implemented, a `docker-compose.yml` plus images.

## 1. Create the module

```bash
cp -R labs/_template labs/week07
```

Update `labs/week07/lab.yaml`:

- `id` and `week` must match the directory.
- Keep `status: planned` until the lab is tested.
- Define measurable learning objectives.
- Declare every container, its internal ports and expected services.
- Confirm `safety.privileged`, `safety.host_network` and
  `safety.external_ports` remain empty/false.
- Declare reset strategy and evidence artefacts.
- Never include assessment answers, instructor passwords or private keys.

## 2. Add networks

Networks use the common convention:

| Week | IoT subnet | Management subnet |
| --- | --- | --- |
| 07 | `10.231.7.0/24` | `10.232.7.0/24` |
| 18 | `10.231.18.0/24` | `10.232.18.0/24` |

Create them with:

```bash
scripts/networks.sh ensure week07
```

The manifest and Compose file must reference the matching
`iotlab_w07_iot` and `iotlab_w07_mgmt` external networks. Never publish a
vulnerable service with Compose `ports:`.

## 3. Build images

Place each image under `labs/week07/images/<name>/` with a pinned base image.
Use non-root users, `read_only: true`, `cap_drop: ALL` and
`no-new-privileges:true` unless the exercise has a reviewed exception.

Images are tagged:

```yaml
image: iotlab/week07-target:${IOTLAB_VERSION:-0.1.0}
```

## 4. Manager integration

The Lab Manager and privileged helper support any lab that follows the standard
scripts, manifest and Compose conventions. No web changes are required.

- The helper validates the lab ID and requires `status: implemented`.
- Start, stop, reset and status call the same fixed scripts listed in
  `docs/lab-manager.md`.
- Evidence listing and reading use the standard `iotlab_wNN_evidence` volume.
- Planned labs appear in the UI but cannot be started.
- Set `module_type: assessment` for capstone modules if they must be displayed
  with the assessment badge.

Do not add new action names, arbitrary paths or shell commands to the helper.
New lifecycle behaviour belongs in the standard scripts.

## 5. Add lifecycle expectations

Compose volumes that contain disposable state must have:

```yaml
labels:
  iotlab.lab: week07
  iotlab.role: state
```

The evidence volume must be named `iotlab_w07_evidence` and labelled:

```yaml
labels:
  iotlab.lab: week07
  iotlab.role: evidence
```

Mount evidence at `/evidence` in containers that produce artefacts. Reset keeps
this volume, so it must not contain answer keys or instructor-only data.

## 6. Health checks and expected services

Every target container needs a health check; `lab-start.sh` waits for healthy
containers. Add each service to `expected_services` and ensure its port is also
listed in the container's `internal_ports`.

## 7. Local validation

```bash
python tools/validate_labs.py .
docker compose -f labs/week07/docker-compose.yml config
scripts/lab-build.sh week07
scripts/lab-start.sh week07
scripts/lab-status.sh week07
scripts/lab-reset.sh week07 --yes
```

Add integration tests under `tests/` covering:

- container health,
- Nmap discovery of expected ports,
- no host-published ports,
- isolation from other networks and the internet,
- reset restoring state while preserving evidence.

## 8. Mark implemented

Only after tests pass and evidence has been reviewed:

```yaml
status: implemented
```

Update `README.md`, `CHANGELOG.md`, `TODO.md` and the acceptance report, then
run the full suite:

```bash
scripts/verify.sh --integration
```

## Review checklist

- [ ] Manifest validates without errors.
- [ ] No `ports:`, `privileged: true` or `network_mode: host`.
- [ ] Base images pinned; no `latest`.
- [ ] No secrets, keys, answers or instructor credentials committed.
- [ ] Internal networks only.
- [ ] Health checks pass from a clean build.
- [ ] Reset works and evidence survives.
- [ ] Documentation and tests updated.
- [ ] No push to GitHub without explicit approval.
