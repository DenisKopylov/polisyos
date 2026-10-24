# GYD-17: родитель и соединение рабочих результатов

Canonical title: V2 real B2 end-to-end loop proof. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/06-verification.md#GYD-17).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [GYD-17.case-binding](../cards/GYD-17/case-binding.md) | [G06](../groups/G06.md) | A permitted real case, trigger authority, production access and actual measurement/evidence owner are source-bound before invocation. |
| [GYD-17.production-trigger](../cards/GYD-17/production-trigger.md) | [G03](../groups/G03.md) | One authorized canonical HTTP ControlWorker→WorkspaceLoop run persists the actual graph and named records to CAS. |
| [GYD-17.evidence-readback](../cards/GYD-17/evidence-readback.md) | [G10](../groups/G10.md) | Fresh downstream consumers resolve the complete artifact graph, recompute byte hashes/provenance and obtain authorized measurement-root validation or exact honest ceiling. |

## Реальный join

Root reconciles the case authorization, one persisted production run and fresh CAS/evidence-owner result under the same source/run/rule identity.

**Outputs:** [GYD-17.case-binding](../cards/GYD-17/case-binding.md), [GYD-17.production-trigger](../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../cards/GYD-17/evidence-readback.md).

**Fresh consumer / ответственный контур:** Fresh downstream consumer resolving WorkspaceContract, graph, SearchLedger, FrontierSnapshot and SearchExitContract from the production CAS run.

**Review размера:** Authorization, one invocation and persisted readback are separate checkpoints; refusal remains diagnostic unless the original honest-ceiling condition is met.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Accepted source/oracle/implementation/probe/review remain the original parent conditions.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **binding** — Post-review closure and actual frozen source/profile remain parent conditional acceptance.
  `task.completion_rule`; `task.acceptance_evidence_requirements[0]`
- **binding** — DES-10 replay identity, quality/reference clauses and UNRUN status are source-bound companions, not authority delegated here.
  `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`
- **join** — Preferred solution bundles case authorization, one HTTP trigger/CAS persistence and fresh consumer plus evidence-owner validation; the three cards own these subclauses.
  `solution.preferred_solution`
- **join** — The four subclaims are route proof, measurement-root proof, persisted artifact and consumer readback; reconcile all three card outputs.
  `solution.composition_contracts[0]`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
