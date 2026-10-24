# DEB-10: родитель и соединение рабочих результатов

Canonical title: Independent print and accessibility evidence. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-10).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-10.accessibility-evidence](../cards/DEB-10/accessibility-evidence.md) | [G10](../groups/G10.md) | Independent report supports only its exact content/carrier/sample/criteria/evaluator/time scope; sample limits remain visible. |
| [DEB-10.ds18-print-reconciliation](../cards/DEB-10/ds18-print-reconciliation.md) | [G08](../groups/G08.md) | The second DS18 checkpoint is preserved append-only and binds exact current content, browser and print instance, only adding schema version if original cannot represent it. |

## Реальный join

accessibility-evidence emits Content-bound pass/partial/limited/contested assessment with sample and time limitations.; ds18-print-reconciliation emits Append-only second-checkpoint record referencing first and current exact print instance, or existing-schema admission.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh scoped accessibility verifier and runtime-dashboard apps/runtime-dashboard/src/shared/export/printExport.ts print consumer.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-10.accessibility-evidence](../cards/DEB-10/accessibility-evidence.md), [DEB-10.ds18-print-reconciliation](../cards/DEB-10/ds18-print-reconciliation.md).

**Fresh consumer / ответственный контур:** Fresh scoped accessibility verifier and runtime-dashboard apps/runtime-dashboard/src/shared/export/printExport.ts print consumer.

**Review размера:** Independent accessibility assessment and append-only DS18 print reconciliation have different producers and closure predicates.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This is a shared two-row scope, preservation, or migration constraint; parent_join keeps independent accessibility evidence separate from DS18 checkpoint closure.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.r14_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.question_ids[0]`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.acceptance_discriminators[3]`
- **binding** — This is a shared two-row scope, preservation, or migration constraint; parent_join keeps independent accessibility evidence separate from DS18 checkpoint closure.
  `task.migration`; `task.r19_extension.writer_rule`; `solution.migration_and_rollback`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
