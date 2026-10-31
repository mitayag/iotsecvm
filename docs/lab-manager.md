# Lab Manager and privileged helper

## Components

```text
Browser on student VM
        |
        | HTTP 127.0.0.1:8080
        v
FastAPI Lab Manager (user iotlab, no Docker access)
        |
        | JSON request/response over /run/iotlab/helper.sock (0660 root:iotlab)
        v
iotlab-helper (root, allowlisted operations)
        |
        | fixed scripts only
        v
Docker CLI -> Docker Engine -> isolated lab networks
```

The web process never mounts `/var/run/docker.sock`. The helper is the only
component that invokes Docker, and it only invokes these fixed scripts:

| Action | Script | Mutating |
| --- | --- | --- |
| `start` | `scripts/lab-start.sh <lab>` | yes |
| `stop` | `scripts/lab-stop.sh <lab>` | yes |
| `reset` | `scripts/lab-reset.sh <lab> --yes` | yes |
| `status` | `scripts/lab-inspect.sh <lab>` | no |
| `evidence_list` | `scripts/lab-evidence-list.sh <lab>` | no |
| `evidence_read` | `scripts/lab-evidence-read.sh <lab> <filename>` | no |

Requests are newline-delimited JSON over a Unix stream socket with a 16 KiB
request limit, a 256 KiB response limit and a protocol version. The helper:

- validates `lab` against `week01` through `week18`,
- rejects planned labs and missing Compose files,
- resolves scripts under the release `scripts/` directory only,
- validates evidence filenames and rejects path traversal,
- serialises operations with a global lock and returns `busy` for concurrent
  requests,
- enforces per-action timeouts and truncates captured output,
- optionally checks peer UIDs on Linux and supports a socket group and mode.

## Local development

```bash
make venv
make helper    # terminal 1, creates /tmp/iotlab-helper.sock
make manager   # terminal 2, http://127.0.0.1:8080
```

The development helper runs as the current user; production runs it as root
through systemd. Stop both processes with Ctrl-C after testing.

## API

The manager binds to `127.0.0.1:8080`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Manager/helper availability and action mode |
| GET | `/api/labs` | All 18 modules with availability and type |
| GET | `/api/labs/{id}` | Detail, expected services, device inventory, networks |
| GET | `/api/labs/{id}/instructions` | README markdown content |
| GET | `/api/labs/{id}/status` | Live container health/status via helper |
| POST | `/api/labs/{id}/actions/start` | Start an implemented lab |
| POST | `/api/labs/{id}/actions/stop` | Stop an implemented lab |
| POST | `/api/labs/{id}/actions/reset` | Reset state and preserve evidence |
| GET | `/api/labs/{id}/evidence` | Runtime volume and host directory listings |
| GET | `/api/labs/{id}/evidence/{filename}` | Read one evidence file safely |

Errors use a structured `detail` object with `message`, `code` and, for failed
commands, captured `result.stdout` / `result.stderr`.

## Action gating

- `IOTLAB_ENABLE_ACTIONS=1` is set by the systemd manager unit.
- If the helper socket is absent or unreachable, `/api/health` reports
  `actions_enabled=false`; mutation endpoints fail with HTTP 503.
- If actions are disabled, mutation endpoints fail with HTTP 403.
- Only Week 1 is implemented; planned labs return HTTP 409.

The manager never falls back to running local commands when the helper is
unavailable.

## Evidence

The runtime evidence volume is `iotlab_w01_evidence`, mounted at `/evidence`.
Reset removes only volumes labelled `iotlab.role=state`. The manager can list
the volume through the helper and can also list/read the host mirror under
`var/evidence/week01`.

Evidence file reads are capped at 32 KiB per file. File names are limited to
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}` and traversal sequences are rejected.

## Student SSH keys

`scripts/gen-lab-keys.sh` creates the Ed25519 key pair under `var/secrets/`.
Production installs set `IOTLAB_KEY_GROUP=iotlab-students` and mode `0640` for the
private key, `0750` for the secrets directory. Add the student login account to
the `iotlab-students` group so it can read the key and connect to the controller:

```bash
sudo usermod -aG iotlab-students student
```

The key is never committed. Do not copy it into the web document root or
evidence archive.

## Installation

```bash
sudo scripts/install.sh --offline-images images/iotlab-images.tar \
  --wheelhouse wheels --dest /opt/iotlab --yes
```

This installs:

- `iotlab-helper.service` (root, allowlisted operations),
- `iotlab-manager.service` (user `iotlab`, no Docker access),
- `/usr/share/applications/iotlab-manager.desktop`,
- the shared evidence/secrets permissions described above.

The helper socket is `/run/iotlab/helper.sock`, mode `0660`, group `iotlab`.
`/api/health` should report `helper_available=true` and `actions_enabled=true`.

## Failure handling

- Helper down: read-only UI; manager returns 503 for live operations.
- Helper busy: HTTP 409; the UI asks the student to retry.
- Script failure: HTTP 500 with captured stderr and return code.
- Invalid lab/filename/action: HTTP 400/404 and no script execution.
- Planned lab: HTTP 409.
- Timeout: HTTP 504.
