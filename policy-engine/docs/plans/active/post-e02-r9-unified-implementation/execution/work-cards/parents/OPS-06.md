# OPS-06: родитель и соединение рабочих результатов

Canonical title: Tenant, job-read and egress authorization proof. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-06).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-06.read-scope](../cards/OPS-06/read-scope.md) | [G06](../groups/G06.md) | Before content fetch or serialization, authenticated actor, target owner, tenant/cell, action and exact current grant authorize the specific job/artifact read and audience projection. |
| [OPS-06.effect-release](../cards/OPS-06/effect-release.md) | [G06](../groups/G06.md) | A provider/source effect or byte release occurs only when the exact source/query, actor, purpose, recipient and time grant is still valid at the irreversible release boundary. |

## Реальный join

Join separate read/projection and external-effect fences from the same current policy authority; existing actual read consumers must resolve target-owner permission before bytes, and source/effect sinks must re-resolve the precise grant at release. Parent output retains denied/limited status and safe audit projection.

**Outputs:** [OPS-06.read-scope](../cards/OPS-06/read-scope.md), [OPS-06.effect-release](../cards/OPS-06/effect-release.md).

**Fresh consumer / ответственный контур:** Existing job/artifact readers and actual connector/provider release sinks, plus the authorized audit/access receipt consumer.

**Review размера:** Two emission planes are separate because their irreversible boundaries differ; both reuse one semantic policy owner. Parent-wide R17 facts do not appoint another authority. Exact target readers and sink paths are re-enumerated under canonical lease after E02 rebind.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate acceptance, coordination, or shared constraint across read-scope, effect-release; selectors task.deliverable, task.positive, task.adversarial, task.removal, task.surface, task.rollback, task.migration, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.rollback_precedence, task.r17_extension.requirement, task.r17_extension.positive, task.r17_extension.adversarial, task.r17_extension.removal, task.r17_extension.delivery_slices[0], task.r17_extension.delivery_slices[1], task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r17_extension.product_verification, solution.preferred_solution, solution.implementation_steps[0], solution.implementation_steps[1], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.migration_and_rollback, solution.composition_contracts[0], solution.composition_contracts[1], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.deviation_triggers[0], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.input_resolution_rule are reconciled by parent_join against the named card outputs and existing consumer, not implemented as peer-owner work.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.product_verification`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
