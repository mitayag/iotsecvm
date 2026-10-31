# Stage 1 Acceptance Report

Date: 2026-10-31
Version: 0.1.0
Scope: Repository and development foundation for Weeks 1-18

## Verdict

Stage 1 implementation is complete for the repository and Week 1 runtime.
Local validation, integration tests, installation (non-systemd) and an offline
bundle update path were executed. No changes were committed or pushed to
GitHub. CI workflow execution on GitHub and the final x86-64 Ubuntu VM install
remain pending approval and target-host execution.

## Delivered work

| Requirement | Implementation |
| --- | --- |
| Repository structure Weeks 1-18 | `labs/week01` implemented; `labs/week02`-`week18` validated planned manifests |
| Lab module specification | `schema/lab.schema.json`, `labs/*/lab.yaml`, `labs/_template/` |
| Common networking foundation | `scripts/networks.sh`, external internal networks per lab, `compose/README.md` |
| Start/stop/status/reset scripts | `scripts/lab-start.sh`, `lab-stop.sh`, `lab-status.sh`, `lab-reset.sh` |
| Install/update/verify/export scripts | `scripts/install.sh`, `update.sh`, `verify.sh`, `export-offline.sh` |
| GitHub Actions | `.github/workflows/validate.yml`, `build.yml`, `test.yml` |
| Week 1 sample | Camera, Mosquitto gateway, key-only SSH controller in `labs/week01/` |
| Developer documentation | `docs/adding-labs.md`, architecture, security, testing, deployment, ARM64, troubleshooting |
| Test framework | 20 pytest tests across manifests, Compose, backend, deploy and runtime |
| Versioned deploy with rollback | `scripts/deploy.sh`, `rollback.sh`, shared `var/`, history log |

Additional delivered items: evidence import/export, SSH key generation, FastAPI
read-only manager, local student interface, schema cross-validation, pinned
Python dependencies and image versions.

## Executed test evidence

### Manifest and static validation

```text
$ .venv/bin/python tools/validate_labs.py .
validated 18 lab manifest(s), 0 warning(s), 0 errors

$ shellcheck -x scripts/*.sh scripts/lib/*.sh
shellcheck-ok

$ docker compose -f labs/week01/docker-compose.yml config --quiet
compose-ok

$ .venv/bin/python -m compileall -q backend tools tests
compile-ok
```

### Full test suite

```text
$ IOTLAB_SKIP_BUILD=1 .venv/bin/python -m pytest -v tests
...
20 passed, 1 warning in 30.42s
```

Warning: FastAPI's TestClient emits a Starlette deprecation notice about
`httpx`; it does not affect the application or test results.

Coverage highlights:

- all 18 manifests exist and validate,
- Compose renders with no published ports, privileges or host networking,
- images use pinned version tags,
- backend lists labs and refuses mutations by default,
- two-release deploy and rollback preserve evidence and history,
- containers report healthy,
- Nmap finds camera 8080/8554, gateway 1883 and controller 22,
- both lab networks report `Internal=true`,
- IoT network cannot reach the controller or internet,
- controller accepts the generated student key,
- MQTT publish succeeds,
- reset removes state, preserves evidence and restarts healthy containers.

### x86-64 images

The local host is arm64, so explicit `linux/amd64` images were built and run:

```text
amd64 build ok: camera
amd64 build ok: gateway
amd64 build ok: controller
linux/amd64

$ IOTLAB_SKIP_BUILD=1 .venv/bin/python -m pytest -v -m integration tests/test_week01_integration.py
8 passed in 21.57s
```

### Installation and interface

`scripts/install.sh --dest /tmp/iotlab-install-final --no-systemd --yes`
completed deployment, dependency installation, key generation and verification.
The installed manager was started with Uvicorn and returned:

```text
{"status":"ok","version":"0.1.0","actions_enabled":false}
18 False
```

The frontend `/` returned the expected HTML shell. The systemd unit was not
installed because the workstation is not the target Ubuntu VM.

### Offline export and update

`scripts/export-offline.sh --skip-build` produced an x86-64 bundle:

```text
dist/iotlab-0.1.0-offline-x86_64.tar.gz
56M
SHA256 b8900f86fd6340187e2cad6ce092f96003cc72108c8ce63bccc9c136a67bba63
```

The bundle contains source, three linux/amd64 images, image provenance, Linux
x86-64 Python wheels and SHA256SUMS. The exporter refuses to package an image
whose architecture differs from the requested platform. `scripts/update.sh`
verified every checksum, loaded the images and switched a temporary deployment
to release `0.1.0`. Wheel installation from the bundle could not be completed
locally because the host Python is macOS/arm64 while the bundle correctly holds
Linux x86-64 wheels; this must be re-executed on the Ubuntu 24.04 x86-64 target.

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Repository structure complete | Pass | 18 lab directories plus platform directories |
| Compose configurations validate | Pass | `docker compose config` |
| Week 1 targets build and start | Pass | arm64 and linux/amd64 builds; healthy containers |
| Nmap discovers intended devices | Pass | Integration tests 2-3 |
| Network isolation passes | Pass | Internal network and egress tests |
| Reset restores initial state | Pass | State marker removed; evidence retained |
| CI tests run successfully | Partial | Workflows validated locally; GitHub run pending push approval |
| Deployment documentation available | Pass | `docs/deployment.md` |
| No push without approval | Pass | No git push or commit performed |

## Deviations and notes

- Lab subnets use `10.231.N.0/24` and `10.232.N.0/24`. The original draft used
  `172.31.0.0/16`, which conflicted with an existing local Docker network.
- Local runtime validation used Linux amd64 images through Docker emulation on
  an arm64 host. Native Ubuntu 24.04 x86-64 execution is still required.
- The current offline bundle is linux/amd64 and was produced on an arm64 host
  through Docker emulation. Native x86-64 wheel installation and service start
  still need verification on the Ubuntu VM.
- The FastAPI mutation API is disabled by default. A privileged helper design
  is deferred to Stage 2.
- Weeks 2-18 are manifests only by design.
- The repository was not initialized, committed or pushed. Awaiting explicit
  approval.

## Blockers

None for completing Stage 1 code. Proceeding to Stage 2 is blocked pending:

1. explicit approval to commit and push the Stage 1 repository,
2. execution of GitHub Actions on the repository,
3. an Ubuntu 24.04 LTS x86-64 VM smoke test of the offline bundle,
4. selection of the Stage 2 lab set.
