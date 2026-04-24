# Runbooks

> Операционная память для Phase 6: от symptoms и triage до rollback и
> blameless postmortem.

Owner: `@platform-owners`
Last tested: `2026-04-17` against the current runbook set, docs inventory, and platform acceptance audit ledger.
Evidence path: `docs/reference/documentation-inventory.md`; `docs/archive/reports/platform-acceptance.md`
Rollback path: use the specific linked runbook for the failing surface; this index is a routing page, not the execution procedure itself.

Каждый runbook в этом разделе обязан отвечать на одни и те же вопросы:

- какой симптом видит дежурный;
- какие причины вероятнее всего;
- какой timeline нужно зафиксировать сразу;
- что делать в первые 15 минут;
- как откатиться или снизить blast radius;
- кто владеет эскалацией;
- какой follow-up обязателен после стабилизации.

## Runbook Set

| Runbook                                                                                               | Когда использовать                                                                        | Primary owner                       |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------- |
| [Dependency Upgrade Regression](dependency-upgrade-regression.md)                                     | После dependency bump, lock refresh или toolchain upgrade пошли регрессии                 | `@platform-owners`                  |
| [Runtime API Outage](runtime-api-outage.md)                                                           | Runtime HTTP surface недоступен, деградировал или отдаёт массовые `5xx`                   | `@runtime-owners`                   |
| [CAS or OPA Outage](cas-opa-outage.md)                                                                | Runtime read/authz paths деградировали из-за CAS, integrity или OPA dependency failure    | `@runtime-owners`                   |
| [Broken Contract Generation](broken-contract-generation.md)                                           | Падает schema/OpenAPI/frontend contract freshness                                         | `@platform-owners`                  |
| [Artifact Signing or SBOM Failure](artifact-signing-sbom-failure.md)                                  | Подпись артефактов, SBOM gate или SLSA payload сломались                                  | `@platform-owners` + security       |
| [Key Rotation](key-rotation.md)                                                                       | Плановая или аварийная ротация signing keys и trust store                                 | `@platform-owners` + security       |
| [Canary Rollback or Failed Promotion](canary-rollback-or-promotion-failure.md)                        | Staged rollout или production promotion остановлены либо откатились                       | `@platform-owners`                  |
| [Idempotency Incident](idempotency-incident.md)                                                       | Retry/replay path создал дубликаты, mismatch или stuck pending state                      | `@runtime-owners`                   |
| [Mutation Audit Investigation](mutation-audit-investigation.md)                                       | Нужно установить кто, когда и что изменил в runtime mutation path                         | `@runtime-owners`                   |
| [Cache Rebuild Storm](cache-rebuild-storm.md)                                                         | Run/timeline/lineage cache services ушли в rebuild storm и бьют по latency/CPU            | `@runtime-owners`                   |
| [Fabric Quarantine/DLQ And Data-Plane Recovery](fabric-quarantine-dlq-and-data-plane-recovery.md)     | Fabric quarantine/DLQ, streaming checkpoint, or connector recovery path needs safe replay | `@fabric-owners`                    |
| [Runtime Graceful Shutdown or Stuck Background Worker](runtime-graceful-shutdown-and-stuck-worker.md) | Shutdown hangs, live connections не дренируются, worker/executor застрял                  | `@runtime-owners`                   |
| [Replay or Restore Workflow](replay-or-restore.md)                                                    | Нужно восстановить replay session, checkpoint path или retained archive                   | `@platform-owners` + affected owner |
| [Retained Artifact Recovery](retained-artifact-recovery.md)                                           | Нужно восстановить retained CI/benchmark/audit/snapshot/archive artifact family           | `@platform-owners` + affected owner |
| [Artifact Corruption Recovery](artifact-corruption-recovery.md)                                       | Read-time integrity verification выявила corrupted blob или manifest mismatch             | `@platform-owners` + affected owner |
| [Docs Publication Failure](docs-publication-failure.md)                                               | `mkdocs build --strict` или repo-tracked documentation gate не проходит                   | `@docs-owners`                      |
| [Benchmark Regression Triage](benchmark-regression-triage.md)                                         | Benchmark suite ушёл вниз по quality, latency или stability                               | `@foundry-owners`                   |

## Postmortem Minimum

Каждый инцидент после стабилизации должен оставить один и тот же минимум:

- UTC timeline с точкой обнаружения, точкой mitigation и точкой восстановления;
- blast-radius statement;
- owner на remediation;
- action items с датами;
- ссылку на изменённый runbook, если в процессе выяснилось, что он был неполным.

Связанные политики:

- [SLO and Error Budget Policy](../reference/operations/slo-error-budget.md)
- [Platform Architecture Diagrams](../reference/operations/platform-architecture-diagrams.md)
- [Observability Topology](../reference/operations/observability-topology.md)
- [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md)
- [Handoff and Platform Review](../reference/operations/handoff-and-platform-review.md)
