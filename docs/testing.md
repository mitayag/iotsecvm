# Testing

## Test layers

| Layer | Location | Purpose |
| --- | --- | --- |
| Manifest/schema | `tests/test_manifests.py` | 18 modules, schema and safety invariants |
| Compose | `tests/test_compose_config.py` | Rendering, no published ports, pinned images |
| Helper | `tests/test_helper.py` | Allowlists, fixed scripts, busy lock, timeouts |
| Backend | `tests/test_backend.py` | Read-only default, actions, status, errors, instructions |
| Deployment | `tests/test_deploy.py` | Versioned deploy and rollback |
| Manager E2E | `tests/test_manager_e2e.py` | Manager start/stop/reset/status/evidence and Week 1 validation |
| Integration | `tests/test_week01_integration.py` | Runtime, Nmap, SSH, isolation, reset |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r tests/requirements-dev.txt
```

## Full suite

```bash
.venv/bin/python -m pytest -v tests
```

`test_week01_integration.py` builds and starts Week 1 unless images already
exist. To skip the build in a repeated run:

```bash
IOTLAB_SKIP_BUILD=1 .venv/bin/python -m pytest -v -m integration tests
```

## What the integration suites prove

- the manager starts, stops and resets Week 1 through the helper socket,
- the helper rejects planned labs, invalid IDs, traversal and unknown actions,
- the helper serialises concurrent operations,
- camera, gateway and controller reach healthy state,
- camera HTTP returns the virtual device status,
- Nmap finds camera 8080/8554, gateway 1883 and controller 22,
- the controller accepts the generated student key,
- both lab networks report `Internal=true`,
- Compose reports no published host ports,
- the IoT network cannot reach the controller or the internet,
- MQTT publishes succeed inside the lab,
- manager instructions and evidence listing/reading work,
- reset removes camera state, preserves evidence and restarts healthy services.

## Manual evidence

Keep the command output used for acceptance reports. For example:

```bash
scripts/lab-status.sh week01 | tee /tmp/status.txt
.venv/bin/python -m pytest -v tests | tee /tmp/pytest.txt
```

Do not claim a test passed without the corresponding executed output.

## CI

- `.github/workflows/validate.yml` validates manifests, Compose rendering,
  shell lint and Python compilation.
- `.github/workflows/build.yml` builds the three Week 1 images and can push to
  GHCR only on version tags or an explicit manual dispatch with `push=true`.
- `.github/workflows/test.yml` builds images and runs the full pytest suite.
