# Week 01: Lab Environment and IoT Asset Discovery

Status: implemented

## Scenario

The laboratory simulates a small managed IoT deployment. A virtual camera sits
on the IoT segment, an MQTT gateway bridges the IoT and management segments,
and an SSH controller is reachable only from the management segment. No lab
service is published to the host.

## Start

From the repository root:

```bash
scripts/gen-lab-keys.sh week01
scripts/lab-build.sh week01
scripts/lab-start.sh week01
scripts/lab-status.sh week01
```

The controller authorises the public key generated under `var/secrets/`.
Private keys are never committed.

## Discover

Run the scanner from a container attached to each lab network:

```bash
docker run --rm --network iotlab_w01_iot instrumentisto/nmap:7.95-r0 \
  -sT -Pn -n -p 22,1883,8080,8554 10.231.1.0/24

docker run --rm --network iotlab_w01_mgmt instrumentisto/nmap:7.95-r0 \
  -sT -Pn -n -p 22,1883,8080,8554 10.232.1.0/24
```

Expected results:

| Network | Host | Port | Service |
| --- | --- | --- | --- |
| iot | camera | 8080 | camera HTTP API |
| iot | camera | 8554 | RTSP-like control |
| iot | gateway | 1883 | MQTT |
| mgmt | gateway | 1883 | MQTT |
| mgmt | controller | 22 | SSH |

Record the scan output in the evidence volume, for example:

```bash
docker run --rm --network iotlab_w01_iot instrumentisto/nmap:7.95-r0 \
  -sT -Pn -n -p 22,1883,8080,8554 10.231.1.0/24 \
  > /tmp/nmap-baseline.txt
```

Use `scripts/lab-evidence.sh import week01 <file>` to place evidence in the
preserved volume, and `scripts/lab-evidence.sh export week01 <directory>` to
retrieve it.

## Reset

```bash
scripts/lab-reset.sh week01 --yes
```

Reset removes camera and broker state, recreates healthy containers and keeps
the evidence volume intact.

## Safety

The MQTT broker intentionally permits anonymous access. That behaviour is
confined to internal Docker networks and must never be published or bridged to
the campus network.
