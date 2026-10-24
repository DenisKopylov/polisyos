# OPS-09: родитель и соединение рабочих результатов

Canonical title: Hybrid private-source worker cell. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-09).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-09.site-execution](../cards/OPS-09/site-execution.md) | [G09](../groups/G09.md) | A selected site worker consumes one valid existing durable job/lease generation and emits a source/version-bound attempt result or explicit unresolved outcome while raw data and secret remain in the custodian boundary. |
| [OPS-09.output-release](../cards/OPS-09/output-release.md) | [G06](../groups/G06.md) | Only the exact cleared result reaches the granted recipient after a current source/right and recipient/output decision at the irreversible release boundary; completed execution or encryption alone is insufficient. |

## Реальный join

Compose source-side attempt receipt from `site-execution` with actual release-time grant/copy/sink receipt from `output-release`, then deliver to CAP-06 intake and CNT-06 inference consumer. Only a selected site profile requires this composition; source permission, output admissibility and scientific meaning each retain their native consumer.

**Outputs:** [OPS-09.site-execution](../cards/OPS-09/site-execution.md), [OPS-09.output-release](../cards/OPS-09/output-release.md).

**Fresh consumer / ответственный контур:** Existing LIF-04 lease/receipt consumer, CAP-06 result intake, OPS-06 actual source/output-right sink, LIF-05 copy/retention reader, CNT-06 inference consumer.

**Review размера:** Site execution and allowed-output release are separate authority/failure planes. Site does not own a queue, private-result authority, source license, copy inventory or inference; selected activation and no-parity status remain explicit.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate acceptance, coordination, or shared constraint across site-execution, output-release; selectors task.deliverable, task.positive, task.adversarial, task.removal, task.surface, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.rollback_precedence, solution.deviation_triggers[0], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.inputs_to_resolve[2], solution.input_resolution_rule are reconciled by parent_join against the named card outputs and existing consumer, not implemented as peer-owner work.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
