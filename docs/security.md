# Security model

## Non-negotiable controls

- No lab target is published on a host interface.
- Lab networks are Docker internal bridges.
- No container uses privileged mode or host networking.
- No Docker socket is mounted into any student-facing container or service.
- No instructor credentials, student private keys or assessment answers are
  committed.
- The manager binds to `127.0.0.1` only.
- Images use pinned versions, never `latest`.

## Container controls

Week 1 applies:

| Service | User | Root filesystem | Capabilities | Privilege escalation |
| --- | --- | --- | --- | --- |
| camera | 10001 | read-only | dropped | blocked |
| gateway | 1883 | read-only | dropped | blocked |
| controller | container root for sshd | writable | default | blocked |

The SSH controller requires a writable filesystem for `/run` and host keys.
It is not privileged and does not use host networking. It accepts only public
key authentication for the unprivileged `labuser` account.

The MQTT broker permits anonymous access intentionally, as a Week 1 discovery
target. This is safe only because the network is internal and the broker is not
published. Do not reuse this configuration outside the lab.

## Secrets

- `scripts/gen-lab-keys.sh` creates Ed25519 keys under `var/secrets/`.
- Development mode uses `0700` for the directory and `0600` for the private key.
- Production installs set `IOTLAB_KEY_GROUP=iotlab-students`, `0750` for the directory,
  and `0640` for the private key. Add the student account to the `iotlab-students` group.
- `.gitignore` excludes keys, `var/` runtime data and `dist/` bundles.
- Docker Compose exposes only the public key as a secret to the controller.
- The web manager is not a member of `iotlab-students` and does not read or
  store private keys.

## Evidence

Evidence volumes use the label `iotlab.role=evidence`. Reset removes only
`iotlab.role=state` volumes. Updates replace the application tree, not shared
`var/` storage. Students can export evidence with
`scripts/lab-evidence.sh export`.

## Manager and helper boundary

- The FastAPI process runs as `iotlab` and never receives the Docker socket.
- Mutation requests go to `iotlab-helper` over `/run/iotlab/helper.sock`,
  mode `0660`, group `iotlab`.
- The helper runs as root only because Docker access requires it. It accepts a
  versioned JSON protocol, validates lab IDs and filenames, and executes only
  fixed scripts under `scripts/`.
- No request field can choose a script, path, shell fragment or Compose file.
- A global helper lock prevents concurrent resets and starts from corrupting
  state.
- Peer UIDs are checked when the platform exposes `SO_PEERCRED` (Linux).
- With `IOTLAB_ENABLE_ACTIONS=0`, or when the helper is unavailable, mutation
  endpoints return 403/503 and no command runs.

See `docs/lab-manager.md` for the protocol and API.

## Platform assumptions

- The student VM is single-user and trusted at the host level.
- Docker Engine is installed and updated by the institution.
- Lab users cannot alter Docker daemon configuration.
- The campus network cannot route to the internal Docker subnets.
- Vulnerability exploitation stays inside reviewed lab targets.

## Reporting

Instructors should review new lab images for privileged requirements, published
ports, secrets and network egress before marking a lab `implemented`.
