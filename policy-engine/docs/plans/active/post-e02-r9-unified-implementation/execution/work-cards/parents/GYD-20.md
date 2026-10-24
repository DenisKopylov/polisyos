# GYD-20: родитель и соединение рабочих результатов

Canonical title: V5 three-level replay audit. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/06-verification.md#GYD-20).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [GYD-20.deterministic-replay](../cards/GYD-20/deterministic-replay.md) | [G10](../groups/G10.md) | One criterion-bearing deterministic operation replays byte-identically under matching input, parameters, seed, code/rule/schema, container and dependency profile. |
| [GYD-20.trace-reconstruction](../cards/GYD-20/trace-reconstruction.md) | [G03](../groups/G03.md) | Persisted DAG, decisions and provenance reconstruct without live model/web call; provider/version uncertainty and redacted content stay explicit. |
| [GYD-20.artifact-revalidation](../cards/GYD-20/artifact-revalidation.md) | [G07](../groups/G07.md) | Promoted artifact refs resolve from CAS and byte digest/size are recomputed; historical and current rule results stay separate. |

## Реальный join

Root reconciles the exact-profile replay receipt, offline trace reconstruction and promoted-artifact revalidation without treating byte equality as authority.

**Outputs:** [GYD-20.deterministic-replay](../cards/GYD-20/deterministic-replay.md), [GYD-20.trace-reconstruction](../cards/GYD-20/trace-reconstruction.md), [GYD-20.artifact-revalidation](../cards/GYD-20/artifact-revalidation.md).

**Fresh consumer / ответственный контур:** Fresh V5 consumer resolving replay outputs, persisted trace and promoted CAS references under their own source/rule identities.

**Review размера:** The three claims are distinct and each really consumes GYD-17’s persisted run component. No live provider call, second V2 loop or historical rewrite.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Task outcome/acceptance and common source profile, timing, companions and review combine all three distinct V5 evidence planes.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.final_execution_property`; `task.completion_rule`; `task.acceptance_evidence_requirements[0]`
- **binding** — Extension refs, R19 status, quality and composition references remain source context.
  `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **join** — The preferred solution explicitly separates deterministic replay, offline trace reconstruction and promoted-artifact revalidation under one frozen profile.
  `solution.preferred_solution`
- **join** — The bundled resource clause names one deterministic replay, offline trace reconstruction and one artifact walk; those are the three cards’ exact workloads.
  `solution.free_grow.resource_behavior`
- **join** — Positive closeout requires all three specific V5 receipts, not any one alone.
  `solution.acceptance_discriminators[0]`
- **join** — The removal clause spans replay binding and semantic-time hashing; reconcile deterministic and artifact receipts.
  `solution.acceptance_discriminators[2]`
- **binding** — Accepted operation classes, V2 artifacts, replay profile, rule versions and shared source-input classification remain parent inputs.
  `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
