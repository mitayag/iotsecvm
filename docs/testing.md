# Testing

## Test layers

| Layer | Location | Purpose |
| --- | --- | --- |
| Manifest/schema | `tests/test_manifests.py` | 18 modules, schema and safety invariants |
| Compose | `tests/test_compose_config.py` | Rendering, no published ports, pinned images |
| Backend | `tests/test_backend.py` | Read-only FastAPI behaviour |
| Deployment | `tests/test_deploy.py` | Versioned deploy and rollback |
| Integration | `tests/test_week01_integration.py` | Runtime, Nmap, isolation, reset |

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

## What the integration suite proves

- camera, gateway and controller reach healthy state,
- Nmap finds camera 8080/8554, gateway 1883 and controller 22,
- both lab networks report `Internal=true`,
- Compose reports no published host ports,
- the IoT network cannot reach the controller or the internet,
- MQTT publishes succeed inside the lab,
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
