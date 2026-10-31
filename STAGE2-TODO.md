# Stage 2 TODO

## Completed

- [x] Constrained privileged helper over a Unix socket.
- [x] Fixed action/script allowlist with lab and filename validation.
- [x] Global operation lock, timeouts and output limits.
- [x] Lab Manager start, stop, reset, status, instructions and evidence APIs.
- [x] Available, planned and assessment module display/filtering.
- [x] Structured errors and operation results in the web interface.
- [x] Helper and manager systemd units.
- [x] Desktop launcher.
- [x] SSH key group permissions for student access.
- [x] Helper unit tests.
- [x] API unit tests.
- [x] Lab Manager end-to-end tests with real containers.
- [x] Week 1 manager validation: HTTP, MQTT, SSH, Nmap, inventory, stop, reset,
      evidence preservation and published-port check.
- [x] x86-64 image/offline architecture checks.

## Remaining for full Stage 2 deployment acceptance

- [ ] Configure a GitHub remote and push the validated repository.
- [ ] Run GitHub Actions and record results.
- [ ] Install on native Ubuntu 24.04 LTS x86-64.
- [x] Prepare `scripts/acceptance-ubuntu.sh` and its acceptance procedure.
- [ ] Execute the prepared acceptance script on Ubuntu.
- [ ] Exercise the root helper through systemd on Ubuntu.
- [ ] Verify desktop launcher and per-student `iotlab` group access on Ubuntu.
- [ ] Execute the full offline wheel install on the Ubuntu target.
- [ ] Have an instructor review the Stage 2 acceptance evidence.

## Explicitly not started

- [ ] Weeks 2-18 runtimes.
- [ ] Assessment harness and answers.
- [ ] Signed bundle verification.
