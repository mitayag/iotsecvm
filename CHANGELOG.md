# Changelog

All notable changes to the HAU IoT Security Virtual Laboratory are recorded here.

## [0.2.0] - 2026-10-31

### Added

- Constrained root helper with a Unix socket, lab/filename allowlists, fixed
  script execution, output limits, timeouts and a global operation lock.
- Functional Lab Manager actions: start, stop, reset, live container status,
  instructions and evidence listing/reading.
- Module type and availability metadata, including assessment classification.
- Filterable student web interface for available, planned and assessment modules.
- Helper and manager systemd units and desktop launcher.
- SSH key group permissions for student access.
- Helper, API and manager end-to-end tests.

### Security

- The web manager has no Docker socket and never executes scripts directly.
- Mutating API calls require the helper and explicit action enablement.
- Evidence reads validate filenames and enforce size limits.
- Concurrency is serialised by the helper.

### Changed

- Version bumped to 0.2.0.
- Lab Manager is no longer read-only when the reviewed helper is installed and
  enabled; it remains read-only when the helper is absent or actions are off.

## [0.1.0] - 2026-10-31

### Added

- Repository foundation for Weeks 1-18.
- Versioned lab manifest schema and validator.
- Common per-lab internal Docker network foundation.
- Lifecycle scripts for build, start, stop, status and reset.
- Evidence preservation and export helper.
- Week 1 sample lab with camera, MQTT gateway and SSH controller.
- FastAPI lab manager and local web interface.
- Installation, verification, offline export, deployment and rollback scripts.
- GitHub Actions workflows for validation, image builds and integration tests.
- Acceptance, security, testing, ARM64 and deployment documentation.
