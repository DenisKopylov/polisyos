# Common Operability Bundle

Owner: `team-core`
Aliases: `common`, `polisyos.common`
Tracked SLO record: exception; recorded dates have elapsed

The repository records an exception expiry of `2026-08-01` and action due date
of `2026-05-31` in [`index.toml`](../index.toml) and [`slo.yaml`](slo.yaml).
Both dates had elapsed by this README review on `2026-10-14`. The repository
records do not establish whether the owner renewed the exception or whether the
external operational state changed. Ask `team-core` for the current disposition
before relying on this page as evidence of an active exception.

`polisyos.common` is a shared helper facade. It does not own standalone
production traffic in Phase 4.9, so dependent component SLOs carry runtime
accountability until Common becomes an operational surface.

Last updated: 2026-10-14

| Asset | Path |
| --- | --- |
| Source README | [src/polisyos/common/README.md](../../../src/polisyos/common/README.md) |
| SLO or exception | [slo.yaml](slo.yaml) |
| Alert mapping | [alerts.yml](alerts.yml) |
| Dashboard mapping | [dashboard.json](dashboard.json) |
| Runbooks and escalation | [runbooks.md](runbooks.md) |
| Runtime contract links | [runtime-contract.toml](runtime-contract.toml) |
| Retention policy links | [retention-policy.toml](retention-policy.toml) |
