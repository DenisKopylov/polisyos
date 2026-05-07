# Runtime Runbooks

Escalation: `team-runtime` primary; `team-platform` is incident commander for
P1 or cross-component outage.

| Alert or symptom | Runbook |
| --- | --- |
| Runtime API or control-plane SLO alerts | [Runtime API Outage](../../../docs/runbooks/runtime-api-outage.md) |
| `RuntimeDependencyCircuitOpen`, `RuntimeRateLimitSaturation`, cell routing alerts | [Runtime API Outage](../../../docs/runbooks/runtime-api-outage.md) |
| `ControlPlaneQueueLagHigh` | [Runtime Graceful Shutdown or Stuck Background Worker](../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md) |
| `RuntimeCacheRebuildStorm`, `RuntimeCacheStalenessHigh` | [Cache Rebuild Storm](../../../docs/runbooks/cache-rebuild-storm.md) |
| Canary rollback or failed promotion | [Canary Rollback or Failed Promotion](../../../docs/runbooks/canary-rollback-or-promotion-failure.md) |

