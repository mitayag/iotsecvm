# Stage 2 Acceptance Report

Date: 2026-10-31
Version: 0.2.0
Scope: Functional Lab Manager, Week 1 end-to-end workflow, deployment checks

## Verdict

Stage 2 is implemented and validated locally. The Lab Manager can start, stop,
reset, inspect and read evidence through a constrained privileged helper. Week 1
was validated end to end through both the CLI and the Lab Manager.

GitHub publication targets `https://github.com/mitayag/iotsecvm.git`, verified
as an empty repository before the first push. Native Ubuntu 24.04 LTS x86-64
execution, root systemd operation and the final GitHub Actions result remain
pending and are recorded in the publication addendum.

## Phase A: Commit and publication

| Item | Result |
| --- | --- |
| Local repository | Initialized on branch `main` |
| Stage 1 commit | `78785ed` - `feat: complete Stage 1 IoT lab foundation` |
| Remote | `origin` -> `https://github.com/mitayag/iotsecvm.git` |
| Remote state before push | Empty repository; no conflicting history |
| Push | Authorized, non-force push to `origin/main` |
| GitHub Actions | Triggered by the push; final results recorded in the publication addendum |
| Secrets / bundles | `var/`, `dist/`, `.venv/`, keys and caches are gitignored |

The Stage 1 commit and Stage 2 changes were audited before publication. No
private keys, generated bundles, student data, local environment files, caches,
instructor answers or unnecessary build artifacts were included.

## Phase B: Functional Lab Manager

Implemented:

- lists all 18 modules with available/planned availability and lab/assessment
  type,
- filterable student interface for all, available, planned and assessment,
- start, stop and reset actions,
- live container health/status with expected services, device inventory and
  network metadata,
- instructions from each module README,
- runtime evidence listing/reading plus host evidence directory listing,
- structured operation results and errors.

### Security controls

| Requirement | Implementation |
| --- | --- |
| No Docker socket in web interface | Manager runs as `iotlab`; no socket mount |
| Allowlisted helper | Root helper with fixed action-to-script table |
| No arbitrary shell/paths | Lab ID regex, filename regex, fixed script paths, no shell |
| Localhost only | Uvicorn binds `127.0.0.1:8080` |
| Preserve evidence | Reset removes only `iotlab.role=state` volumes |
| Prevent concurrent corruption | Global helper lock returns `busy` |
| Read-only without helper | Actions disabled/503 when helper unavailable |

The helper socket is `/run/iotlab/helper.sock`, mode `0660`, group `iotlab`.
Linux peer UID checking is implemented through `SO_PEERCRED`. The helper accepts
only:

`start`, `stop`, `reset`, `status`, `evidence_list`, `evidence_read`, `health`.

## Phase C: Week 1 end-to-end validation

Executed through `tests/test_manager_e2e.py`:

- Lab Manager start: passed.
- Camera HTTP discovery (`http://camera:8080/status`): passed, returned `VC-100`.
- MQTT gateway discovery and publish: passed.
- SSH controller discovery and key authentication: passed, returned `labuser`.
- Nmap: camera 8080/8554, gateway 1883, controller 22 all open.
- Expected services and device inventory returned by the API: passed.
- Lab Manager stop: passed; status returned no containers.
- Reset: passed; camera state marker was removed.
- Evidence preservation: passed; evidence marker survived reset and was readable.
- Published-port check: `published_port_count` was 0.

A real Uvicorn instance was also run on `127.0.0.1:8098` with the helper socket:

```text
/api/health -> {"status":"ok","version":"0.2.0","actions_enabled":true,
                "helper":{"helper_available":true,"helper_version":"1.0"}}
/api/labs   -> 18 modules, 1 available, 1 assessment
POST start  -> status ok, 7150 ms
GET status  -> healthy=True, published_port_count=0,
               services camera/controller/gateway
GET evidence-> runtime_available=True, camera-events.log present
POST stop   -> status ok, 3839 ms
```

## Phase D: Deployment compatibility

### Architecture

```text
camera     linux/amd64
controller linux/amd64
gateway    linux/amd64
```

Images were built for `linux/amd64` and run under Docker emulation on the
macOS arm64 development host.

### Offline bundle

```text
dist/iotlab-0.2.0-offline-x86_64.tar.gz
56 MiB
SHA256 ed817a50d4a11f3f02a59d867db9071eb903c89aa91522e900c6ddd0ec25cce0
```

Checksums, image load and offline dependency installation were executed:

- `shasum -a 256 -c SHA256SUMS`: passed.
- `docker load` of all three images: passed.
- Linux x86-64 wheel install in `python:3.12.8-slim-bookworm`: passed.
- Imports of FastAPI, schema, manager and helper: passed.
- Offline manifest validation: 18 manifests, 0 errors.

### Installation and desktop

Non-systemd install to a temporary destination completed and verified at version
0.2.0. The desktop file passes `desktop-file-validate`. Deployment asset tests
confirm the manager unit has no Docker socket, the helper uses root plus an
allowlist, and the launcher points at `http://127.0.0.1:8080`.

Native Ubuntu installation, the root systemd helper, `/usr/share/applications`
installation and `iotlab-students` group access were **not executed** on this macOS host.

### macOS vs Ubuntu differences

| Area | macOS development | Ubuntu target |
| --- | --- | --- |
| Docker | Docker Desktop, emulated linux/amd64 | Native Docker Engine |
| Service manager | None | systemd helper + manager |
| Root helper | Run as local user in tests | Root `iotlab-helper.service` |
| Peer UID check | Skipped (`SO_PEERCRED` unavailable) | Enforced |
| Desktop integration | File validation only | `/usr/share/applications` plus `xdg-open` |
| Key group | Not created | `iotlab-students` group and `0640` keys |
| Offline wheels | Installed in linux/amd64 container | Installed by installer |

## Tests

Final local run:

```text
61 passed, 1 skipped, 1 warning in 63.47s
```

The skipped test is Linux-only peer UID rejection; it is expected to run in
GitHub Actions on Ubuntu. The warning is FastAPI's TestClient `httpx`
deprecation notice and does not affect results.

Additional checks:

```text
validated 18 lab manifest(s), 0 warning(s), 0 errors
shellcheck: pass
docker compose config: pass
Python compileall: pass
node --check frontend/app.js: pass
desktop-file-validate: pass
```

No final test failed. No failed test is being hidden or marked successful
without execution.

## Remaining work

See `STAGE2-TODO.md`:

1. configure a GitHub remote and publish,
2. run GitHub Actions,
3. install and test on native Ubuntu 24.04 x86-64,
4. exercise the root helper and desktop launcher,
5. complete offline wheel installation on the target,
6. obtain instructor review before starting Weeks 2-18.

Weeks 2-18 were not started.
