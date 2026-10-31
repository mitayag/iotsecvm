# HAU IoT Security Virtual Laboratory

An offline-capable, container-based laboratory platform for 18 weeks of IoT
security practical work at Holy Angel University. The student target is a
self-contained Ubuntu 24.04 LTS x86-64 virtual machine running Docker Engine and
Docker Compose. No Kali Linux, Proxmox or AI harness is required at runtime.

**Current stage:** Stage 2, functional Lab Manager, version `0.2.0`. Week 1 is
implemented; Weeks 2-18 have validated planned manifests. Weeks 2-18 runtimes
are intentionally not built yet.

## Safety model

- Every lab uses dedicated internal Docker networks with no external gateway.
- No vulnerable lab service is published on the host.
- Containers run without privileged mode or host networking.
- The unprivileged Lab Manager receives no Docker socket.
- Lab operations pass through an allowlisted root helper over a Unix socket.
- The helper accepts only fixed lab IDs and fixed scripts; it cannot run
  arbitrary shell commands or Compose paths.
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

## Lab Manager (development)

Run the helper and manager in separate terminals:

```bash
make helper
make manager
```

Open `http://127.0.0.1:8080`. Production installs run both through systemd; see
[docs/lab-manager.md](docs/lab-manager.md) and
[docs/deployment.md](docs/deployment.md).

## Verification

```bash
.venv/bin/python -m pytest tests
scripts/verify.sh --integration
```

The test suite verifies manifest and Compose validation, helper allowlisting and
concurrency, Lab Manager start/stop/reset/status/evidence operations, container
health, Nmap discovery, SSH key authentication, network isolation, absence of
published ports, evidence-preserving reset and versioned deploy/rollback.

## Repository layout

```text
.github/workflows/     Validation, image build and integration CI
backend/app/           FastAPI Lab Manager
backend/helper/        Constrained privileged helper and Unix-socket client
compose/               Networking conventions
deploy/                systemd units and desktop launcher
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
- [Lab Manager and helper](docs/lab-manager.md)
- [Adding a weekly lab](docs/adding-labs.md)
- [Deployment and rollback](docs/deployment.md)
- [Testing](docs/testing.md)
- [Security model](docs/security.md)
- [ARM64 requirements](docs/arm64.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Stage 1 acceptance report](ACCEPTANCE.md)
- [Stage 2 acceptance report](ACCEPTANCE-STAGE2.md)
- [Remaining work](TODO.md)
- [Stage 2 TODO](STAGE2-TODO.md)

## Stage boundaries

Stage 1 established the repository, Week 1 sample, lifecycle tooling, CI and
versioned deployment. Stage 2 adds the functional Lab Manager, constrained
privileged helper, desktop launcher and end-to-end Week 1 manager validation.
Weeks 2-18 remain manifests only until explicitly approved.
