# Common Operability Bundle

Owner: `team-core`
Aliases: `common`, `polisyos.common`
Status: explicit SLO exception

`polisyos.common` is a shared helper facade. It does not own standalone
production traffic in Phase 4.9, so dependent component SLOs carry runtime
accountability until Common becomes an operational surface.

| Asset | Path |
| --- | --- |
| Source README | [src/polisyos/common/README.md](../../../src/polisyos/common/README.md) |
| SLO or exception | [slo.yaml](slo.yaml) |
| Alert mapping | [alerts.yml](alerts.yml) |
| Dashboard mapping | [dashboard.json](dashboard.json) |
| Runbooks and escalation | [runbooks.md](runbooks.md) |
| Runtime contract links | [runtime-contract.toml](runtime-contract.toml) |
| Retention policy links | [retention-policy.toml](retention-policy.toml) |

