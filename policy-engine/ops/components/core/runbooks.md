# Core Runbooks

Escalation: `team-core` primary; `team-security` joins immediately for audit,
artifact integrity, or tenant-boundary incidents.

| Alert or symptom | Runbook |
| --- | --- |
| `AuditChainTamperDetected` | [Mutation Audit Investigation](../../../docs/runbooks/mutation-audit-investigation.md) |
| `AuditSinkQueueBackpressure` | [Mutation Audit Investigation](../../../docs/runbooks/mutation-audit-investigation.md) |
| `AuditColdTierWriteFailure` | [Mutation Audit Investigation](../../../docs/runbooks/mutation-audit-investigation.md) |
| `ArtifactIntegrityFailuresDetected` | [Artifact Corruption Recovery](../../../docs/runbooks/artifact-corruption-recovery.md) |
| Idempotency replay mismatch | [Idempotency Incident](../../../docs/runbooks/idempotency-incident.md) |
| CAS or OPA dependency outage | [CAS or OPA Outage](../../../docs/runbooks/cas-opa-outage.md) |

