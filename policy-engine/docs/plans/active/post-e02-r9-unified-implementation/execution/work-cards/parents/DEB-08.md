# DEB-08: родитель и соединение рабочих результатов

Canonical title: Recursive-cycle and cross-scope confidence residuals. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-08).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-08.gap2-composition](../cards/DEB-08/gap2-composition.md) | [G03](../groups/G03.md) | No combined confidence is emitted across scopes without an owner-approved composition rule and explicit dependence assumptions; incompatible scope remains unknown/incomparable. |
| [DEB-08.gap3-transcript](../cards/DEB-08/gap3-transcript.md) | [G03](../groups/G03.md) | Transcript evidence binds actual controlled source, release family, rule version and complete row set; fixtures never count as controlled evidence. |
| [DEB-08.gap5-run-census](../cards/DEB-08/gap5-run-census.md) | [G03](../groups/G03.md) | GY-GAP5 enumerates complete production recursive-cycle runs/rows; fixtures stay outside numerator and repeated views are not new cases. |
| [DEB-08.gap6-row-movement](../cards/DEB-08/gap6-row-movement.md) | [G03](../groups/G03.md) | Each GY-GAP6 row has evidence linking actual re-entry to deeper terminal movement. |
| [DEB-08.ds15-receipt-admission](../cards/DEB-08/ds15-receipt-admission.md) | [G03](../groups/G03.md) | An existing DS15 receipt is admitted by GY against the exact original row and yields a GY closure disposition without a duplicate producer. |

## Реальный join

gap2-composition emits Versioned composition rule or typed blocked/unknown ledger result.; gap3-transcript emits Content-bound controlled transcript receipt and explicit GY admission status.; gap5-run-census emits Recomputable production run/row census with fixture exclusion and provenance.; gap6-row-movement emits Per-row movement receipt and typed GY disposition.; ds15-receipt-admission emits GY register entry referencing DS15 receipt and explicit closure/remaining disposition.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh confidence ledger and GY evidence/register consumers; GY receipt admission is separate from DS15 production.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-08.gap2-composition](../cards/DEB-08/gap2-composition.md), [DEB-08.gap3-transcript](../cards/DEB-08/gap3-transcript.md), [DEB-08.gap5-run-census](../cards/DEB-08/gap5-run-census.md), [DEB-08.gap6-row-movement](../cards/DEB-08/gap6-row-movement.md), [DEB-08.ds15-receipt-admission](../cards/DEB-08/ds15-receipt-admission.md).

**Fresh consumer / ответственный контур:** Fresh confidence ledger and GY evidence/register consumers; GY receipt admission is separate from DS15 production.

**Review размера:** GAP2 decision, GAP3 transcript, GAP5 production census, GAP6 row movement and DS15 receipt admission are five different evidence outcomes.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This fragment binds multiple independent GY evidence rows or a shared population/admission rule; parent_join consumes each named output without counting duplicate views.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **binding** — This fragment binds multiple independent GY evidence rows or a shared population/admission rule; parent_join consumes each named output without counting duplicate views.
  `task.migration`; `solution.composition_contracts[2]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
