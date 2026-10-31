# ARM64 compatibility

Stage 1 supports and is tested on x86-64 only. Do not advertise ARM64 support
until the checks below are completed on physical or emulated ARM64 hardware.

## Required review

1. **Base images**
   - `python:3.12.8-slim-bookworm`, `alpine:3.20.3` and
     `eclipse-mosquitto:2.0.20` must resolve for `linux/arm64`.
   - Record resolved digests in the release manifest.
2. **OpenSSH package**
   - `openssh-server=9.7_p1-r5` must exist for the Alpine 3.20 ARM64 repository.
   - Verify `ssh-keygen -A`, sshd privilege separation and key-only login.
3. **Nmap scanner**
   - `instrumentisto/nmap:7.95-r0` must publish an ARM64 manifest.
   - TCP connect scans (`-sT`) must discover the same ports.
4. **Docker networks**
   - Internal bridge subnets and Docker DNS must operate identically.
5. **Python manager**
   - Build the wheelhouse for `linux/arm64`; do not reuse x86-64 wheels.
   - Confirm FastAPI and Uvicorn start on the target Python runtime.
6. **Offline export**
   - `scripts/export-offline.sh --platform linux/arm64` produces an `aarch64`
     bundle and checks that every image matches the requested platform.
7. **CI**
   - Add a native ARM64 runner or QEMU build job, then run the integration suite
     on ARM64 before marking support complete.

## Gateway testing

The supplied gateway configuration is architecture-independent. ARM64 still
requires validation of Mosquitto persistence volume ownership and health checks.

## Acceptance policy

Until the ARM64 checklist passes with recorded evidence, an ARM64 installation
is unsupported and should be reported as an unverified platform rather than a
working deployment.
