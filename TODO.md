# TODO

## Stage 1: Repository and development foundation

- [x] Create repository structure for Weeks 1-18.
- [x] Define the `lab.yaml` specification and JSON Schema.
- [x] Add common internal Docker network foundation.
- [x] Add start, stop, status, reset and evidence scripts.
- [x] Add install, update, verify and offline export scripts.
- [x] Add GitHub Actions validation, build and test workflows.
- [x] Implement the Week 1 camera, MQTT gateway and SSH controller.
- [x] Add developer documentation for new weekly labs.
- [x] Add automated startup, discovery, isolation and reset tests.
- [x] Add versioned deployment with rollback.
- [x] Run local validation and integration tests.
- [ ] Obtain explicit approval before pushing any changes to GitHub.

## Stage 2 candidate work

- [ ] Implement Weeks 2-5 images and manifests.
- [ ] Replace the disabled manager action path with a privileged helper daemon
      on a Unix socket, with an allow-list and no Docker socket exposure.
- [ ] Add a sudoers-reviewed action path for the systemd manager.
- [ ] Add per-student evidence packaging and instructor collection workflow.
- [ ] Publish signed offline bundles and add signature verification.
- [ ] Add image SBOM retention and vulnerability scanning policy.
- [ ] Build and validate an ARM64 bundle.
- [ ] Evaluate backup/restore for evidence volumes across VM replacement.
- [ ] Add instructor-only assessment harness outside the student repository.

## Known limitations

- Weeks 2-18 are planned manifests only.
- The lab manager mutation API is disabled by default.
- Week 1 is validated on x86-64 only.
- The systemd unit assumes the default `/opt/iotlab` destination.
- `dist/` bundles are not committed and have not been transferred to a VM in
  this stage.
