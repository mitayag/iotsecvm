# Architecture

## Runtime components

```text
Host (Ubuntu 24.04 LTS student VM)
├── Docker Engine + Compose
│   ├── iotlab_w01_iot   (internal bridge, 10.231.1.0/24)
│   │   ├── camera       8080/tcp, 8554/tcp
│   │   └── gateway      1883/tcp
│   ├── iotlab_w01_mgmt  (internal bridge, 10.232.1.0/24)
│   │   ├── gateway      1883/tcp (dual-homed)
│   │   └── controller   22/tcp
│   └── named volumes
│       ├── iotlab_w01_camera_state   (reset removes)
│       ├── iotlab_w01_gateway_data   (reset removes)
│       └── iotlab_w01_evidence       (reset/update preserve)
├── FastAPI lab manager on 127.0.0.1:8080 (read-only default)
└── CLI lifecycle scripts
```

No lab container has a host-published port. The two networks are created with
`--internal`, so containers cannot reach the campus network or the internet.
The gateway is deliberately dual-homed to represent a management bridge.

## Trust boundaries

| Boundary | Control |
| --- | --- |
| Host to lab | No published ports; CLI or local UI only |
| IoT segment to management | Gateway is the only dual-homed service |
| Lab to internet | Internal Docker bridge networks without NAT |
| Student to Docker daemon | No socket mounted; manager actions disabled by default |
| Evidence to reset/update | Dedicated volume labelled `iotlab.role=evidence` |
| Student to instructor answers | Assessment material excluded from repository |

## Image and version policy

- Lab images use the `VERSION` file through `IOTLAB_VERSION`.
- Base images are pinned to explicit tags in Dockerfiles.
- `docker compose` files never use `latest`.
- CI builds the same source that is deployed; release bundles record image IDs
  and repository digests in `images/manifest.txt`.
- Offline bundles are checksummed with SHA256.

## Lifecycle

`lab-start.sh` ensures networks and keys, then runs Compose with health-gated
startup. `lab-stop.sh` stops containers without deleting volumes. `lab-reset.sh`
removes only volumes labelled `iotlab.role=state`, leaving evidence and keys.
`deploy.sh` installs immutable release directories and switches a `current`
symlink; `rollback.sh` restores a prior release.

## Stage 1 limitations

- Week 1 is the only implemented runtime.
- The manager API is read-only by default.
- Automated assessment answers are not present.
- ARM64 is documented but not part of the accepted Stage 1 target.
