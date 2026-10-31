# HAU IoT Security Virtual Laboratory

An offline-capable, container-based laboratory platform for 18 weeks of IoT
security practical work at Holy Angel University. The student target is a
self-contained Ubuntu 24.04 LTS x86-64 virtual machine running Docker Engine and
Docker Compose. No Kali Linux, Proxmox or AI harness is required at runtime.

**Current stage:** Stage 1, repository and development foundation, version
`0.1.0`. Week 1 is implemented; Weeks 2-18 have validated planned manifests.

## Safety model

- Every lab uses dedicated internal Docker networks with no external gateway.
- No vulnerable lab service is published on the host.
- Containers run without privileged mode or host networking.
- The lab manager receives no Docker socket. Mutating API actions are disabled
  by default; lifecycle operations use reviewed scripts.
- Student SSH keys are generated locally under `var/secrets/` and are never
  committed.
- Evidence volumes are preserved across reset and update operations.

## Quick start (development)

Requirements: Docker Engine with Compose v2, Python 3.12+, OpenSSH client tools.

```bash
make venv
scripts/gen-lab-keys.sh week01
scripts/lab-build.sh week01
scripts/lab-start.sh week01
scripts/lab-status.sh week01
```

Discover Week 1 assets from inside the lab networks:

```bash
docker run --rm --network iotlab_w01_iot instrumentisto/nmap:7.95-r0 \
  -sT -Pn -n -p 22,1883,8080,8554 10.231.1.0/24

docker run --rm --network iotlab_w01_mgmt instrumentisto/nmap:7.95-r0 \
  -sT -Pn -n -p 22,1883,8080,8554 10.232.1.0/24
```

Reset while keeping evidence:

```bash
scripts/lab-reset.sh week01 --yes
```

## Verification

```bash
.venv/bin/python -m pytest tests
scripts/verify.sh --integration
```

The test suite verifies manifest and Compose validation, container health, Nmap
discovery, network isolation, absence of published ports, MQTT operation,
evidence-preserving reset and versioned deploy/rollback.

## Repository layout

```text
.github/workflows/     Validation, image build and integration CI
backend/               FastAPI lab manager (read-only by default)
compose/               Networking conventions
deploy/                systemd unit
docs/                  Architecture, authoring, deployment and security guides
frontend/              Lightweight local student interface
labs/_template/        Starting point for a new week
labs/week01/           Implemented Week 1 lab
labs/week02..18/       Planned lab manifests
schema/                JSON Schema for lab.yaml
scripts/               Lifecycle, install, verify, export and deployment tools
tests/                 Unit and integration tests
tools/                 Manifest validator
var/                   Local runtime state, keys and evidence (gitignored)
```

## Documentation

- [Architecture](docs/architecture.md)
- [Adding a weekly lab](docs/adding-labs.md)
- [Deployment and rollback](docs/deployment.md)
- [Testing](docs/testing.md)
- [Security model](docs/security.md)
- [ARM64 requirements](docs/arm64.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Stage 1 acceptance report](ACCEPTANCE.md)
- [Remaining work](TODO.md)

## Stage boundaries

Stage 1 establishes the repository, Week 1 sample, lifecycle tooling, CI and
versioned deployment. Weeks 2-18 are intentionally manifests only until their
stages are approved. The manager's mutating API remains disabled until the
privileged helper design in `TODO.md` is implemented and reviewed.
