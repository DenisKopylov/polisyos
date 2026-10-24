# LIF-08: родитель и соединение рабочих результатов

Canonical title: Compose a second source and its compatibility lifecycle. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/03-lineage.md#LIF-08).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-08.capture_binding](../cards/LIF-08/capture_binding.md) | [G01](../groups/G01.md) | Distinct source binds to actual CAP02 receipt, profile/parser generation and own cut. |
| [LIF-08.directional_semantics](../cards/LIF-08/directional_semantics.md) | [G02](../groups/G02.md) | Only mapped required facets admit; optional unknown inert, required unknown/downgrade limits affected use. |
| [LIF-08.migration_retirement](../cards/LIF-08/migration_retirement.md) | [G07](../groups/G07.md) | Old/new roots coexist; retire only after refs/backup/GC reconcile. |

## Реальный join

Join capture_binding (actual CAP02 source/profile/cut), directional_semantics (reader-specific mapped requiredness), and migration_retirement (roots/old-reader retirement reconciled with LIF07 selected influence, rights and OPS restore). A first-route WDI receipt does not prove a distinct second source.

**Outputs:** [LIF-08.capture_binding](../cards/LIF-08/capture_binding.md), [LIF-08.directional_semantics](../cards/LIF-08/directional_semantics.md), [LIF-08.migration_retirement](../cards/LIF-08/migration_retirement.md).

**Fresh consumer / ответственный контур:** Fresh SourceContract/catalog and selected consumer/API reader; LIF07 descendant reader and OPS-05 restore/old-reader GC consumer only for the selected migration.

**Review размера:** 3 checkpoints; CAP producer/reader semantics/retirement distinct. Pattern pass P01/P02/P05/P07/P08/P10/P29/P32/P37/P38; validate real capture, requiredness removal and safe GC.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Receipt, mapping, reader and trust outputs combine.
  `task.deliverable`; `task.positive[0]`; `task.positive[1]`; `task.adversarial[0]`
- **binding** — Shared acceptance/review/companions.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **binding** — R19 refs/status.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Writer/ref/preferred navigation.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`
- **join** — New transport/trust needs CAP/OPS extension; LIF06 resource accounting conditional.
  `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **join** — Positive, adversarial and removal span owners.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Parent input rule.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
