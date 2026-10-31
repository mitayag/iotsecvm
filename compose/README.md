# Common Docker networking foundation

Every lab uses two dedicated external bridge networks created by
`scripts/networks.sh`. Compose files reference them as `external: true`.

| Week | IoT network | IoT subnet | Management network | Management subnet |
| --- | --- | --- | --- | --- |
| 01 | `iotlab_w01_iot` | `10.231.1.0/24` | `iotlab_w01_mgmt` | `10.232.1.0/24` |
| 02 | `iotlab_w02_iot` | `10.231.2.0/24` | `iotlab_w02_mgmt` | `10.232.2.0/24` |
| ... | ... | ... | ... | ... |
| 18 | `iotlab_w18_iot` | `10.231.18.0/24` | `iotlab_w18_mgmt` | `10.232.18.0/24` |

## Invariants

- `docker network create --internal` is mandatory. Docker supplies no external
  gateway, so lab networks cannot reach the campus network or internet.
- Names include the week, preventing cross-lab traffic by default.
- Compose `ports:` is forbidden. Students reach services through tooling
  containers attached to the authorised network.
- Networks carry `iotlab.lab=<weekNN>` and `iotlab.managed=true` labels.
- `networks.sh` refuses to reuse a network owned by another lab.

## Commands

```bash
scripts/networks.sh ensure week01
scripts/networks.sh status week01
scripts/networks.sh remove week01
```

The Week 1 gateway is intentionally attached to both IoT and management
networks to represent a management bridge. Other labs should justify any
dual-homed service in `lab.yaml` and in security review.
