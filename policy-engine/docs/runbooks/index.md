# Runbooks

> Операционная память для Phase 6: от symptoms и triage до rollback и
> blameless postmortem.

Каждый runbook в этом разделе обязан отвечать на одни и те же вопросы:

- какой симптом видит дежурный;
- какие причины вероятнее всего;
- какой timeline нужно зафиксировать сразу;
- что делать в первые 15 минут;
- как откатиться или снизить blast radius;
- кто владеет эскалацией;
- какой follow-up обязателен после стабилизации.

## Runbook Set

| Runbook | Когда использовать | Primary owner |
|---|---|---|
| [Dependency Upgrade Regression](dependency-upgrade-regression.md) | После dependency bump, lock refresh или toolchain upgrade пошли регрессии | `@platform-owners` |
| [Runtime API Outage](runtime-api-outage.md) | Runtime HTTP surface недоступен, деградировал или отдаёт массовые `5xx` | `@runtime-owners` |
| [Broken Contract Generation](broken-contract-generation.md) | Падает schema/OpenAPI/frontend contract freshness | `@platform-owners` |
| [Artifact Signing or SBOM Failure](artifact-signing-sbom-failure.md) | Подпись артефактов, SBOM gate или SLSA payload сломались | `@platform-owners` + security |
| [Canary Rollback or Failed Promotion](canary-rollback-or-promotion-failure.md) | Staged rollout или production promotion остановлены либо откатились | `@platform-owners` |
| [Replay or Restore Workflow](replay-or-restore.md) | Нужно восстановить replay session, checkpoint path или retained archive | `@platform-owners` + affected owner |
| [Retained Artifact Recovery](retained-artifact-recovery.md) | Нужно восстановить retained CI/benchmark/audit/snapshot/archive artifact family | `@platform-owners` + affected owner |
| [Docs Publication Failure](docs-publication-failure.md) | `mkdocs build --strict` или `docs-pages` publish path не проходит | `@docs-owners` |
| [Benchmark Regression Triage](benchmark-regression-triage.md) | Benchmark suite ушёл вниз по quality, latency или stability | `@foundry-owners` |

## Postmortem Minimum

Каждый инцидент после стабилизации должен оставить один и тот же минимум:

- UTC timeline с точкой обнаружения, точкой mitigation и точкой восстановления;
- blast-radius statement;
- owner на remediation;
- action items с датами;
- ссылку на изменённый runbook, если в процессе выяснилось, что он был неполным.

Связанные политики:

- [SLO and Error Budget Policy](../reference/operations/slo-error-budget.md)
- [Observability Topology](../reference/operations/observability-topology.md)
- [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md)
- [Handoff and Platform Review](../reference/operations/handoff-and-platform-review.md)
