# OPS-12: родитель и соединение рабочих результатов

Canonical title: Conditional air-gapped cell. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-12).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-12.bundle-currentness](../cards/OPS-12/bundle-currentness.md) | [G07](../groups/G07.md) | A selected offline protected read is current only for the exact locally imported signed bundle, monotonic verified generation and independently supported as-of/freshness basis read by a fresh local consumer. |
| [OPS-12.no-egress](../cards/OPS-12/no-egress.md) | [G09](../groups/G09.md) | For a selected offline cell, no unapproved network route transmits source data, secrets or telemetry beyond the declared host boundary; application setting alone never establishes this. |
| [OPS-12.offline-restore](../cards/OPS-12/offline-restore.md) | [G09](../groups/G09.md) | A selected offline restore admits protected reads only when local bundle/runtime/DB/CAS, rights, trust generation and as-of/anti-rollback state reconcile for the fresh local reader. |

## Реальный join

Only if the institution selects an offline profile, join actual local bundle import/currentness, observed no-egress boundary and OPS-05 local restore/rights/trust reconciliation before fresh local protected read. Otherwise preserve an explicit unselected trigger/no-parity scope; unselected is not PASS.

**Outputs:** [OPS-12.bundle-currentness](../cards/OPS-12/bundle-currentness.md), [OPS-12.no-egress](../cards/OPS-12/no-egress.md), [OPS-12.offline-restore](../cards/OPS-12/offline-restore.md).

**Fresh consumer / ответственный контур:** Fresh local protected reader on the exact imported bundle/state, independent host/network traffic observer, and existing OPS-05 restore consumer.

**Review размера:** Three independently falsifiable properties are separate. Offline remains conditional, local as-of is not cloud currentness, no-egress is externally observed, and restore reuses OPS-05; no cloud dependency or new scheduler is introduced.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate acceptance, coordination, or shared constraint across bundle-currentness, no-egress, offline-restore; selectors task.deliverable, task.positive, task.adversarial, task.surface, task.rollback, task.migration, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.rollback_precedence, task.r17_extension.product_verification, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.preferred_solution, solution.free_grow.extension_boundary, solution.migration_and_rollback, solution.composition_contracts[0], solution.inputs_to_resolve[0], solution.input_resolution_rule are reconciled by parent_join against the named card outputs and existing consumer, not implemented as peer-owner work.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.free_grow.extension_boundary`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
