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

## Stage 2: Functional Lab Manager

- [x] Add constrained privileged helper with Unix socket.
- [x] Allowlist lab operations and reject arbitrary commands/paths.
- [x] Add manager start/stop/reset/status/instructions/evidence endpoints.
- [x] Add available/planned/assessment filtering in the web interface.
- [x] Add helper/manager systemd units and desktop launcher.
- [x] Add helper, API and manager end-to-end tests.
- [x] Verify Week 1 manager workflow locally.
- [ ] Publish Stage 1/2 to GitHub (blocked: no remote configured).
- [ ] Run GitHub Actions and record CI status.
- [ ] Execute native Ubuntu 24.04 x86-64 installation and root helper test.

## Deferred

- [ ] Implement Weeks 2-5 images and manifests.
- [ ] Add per-student evidence packaging and instructor collection workflow.
- [ ] Publish signed offline bundles and add signature verification.
- [ ] Add image SBOM retention and vulnerability scanning policy.
- [ ] Build and validate an ARM64 bundle.
- [ ] Evaluate backup/restore for evidence volumes across VM replacement.
- [ ] Add instructor-only assessment harness outside the student repository.

## Known limitations

- Weeks 2-18 are planned manifests only.
- Week 1 is validated locally on linux/amd64 through Docker emulation; native
  Ubuntu x86-64 systemd deployment is still pending.
- The helper root/systemd path has not been exercised on native Ubuntu.
- `dist/` bundles are not committed.
- GitHub publication is blocked because no remote exists.
