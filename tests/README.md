# Test suite

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r tests/requirements-dev.txt
```

## Run

```bash
.venv/bin/python -m pytest tests
```

Integration tests require a reachable Docker daemon and build the Week 1
images. Skip a rebuild when images already exist:

```bash
IOTLAB_SKIP_BUILD=1 .venv/bin/python -m pytest -m integration tests
```

The integration suite verifies container health, Nmap discovery, internal-only
networks, absence of host-published ports, network isolation, MQTT publish and
reset with evidence preservation.
