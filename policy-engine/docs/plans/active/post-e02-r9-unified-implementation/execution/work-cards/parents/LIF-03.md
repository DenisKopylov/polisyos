# LIF-03: родитель и соединение рабочих результатов

Canonical title: Fence capture frontier commits against stale writers. R26 форма: `retain`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/02-custody.md#LIF-03).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-03.conditional_frontier_commit](../cards/LIF-03/conditional_frontier_commit.md) | [G01](../groups/G01.md) | Verified receipt advances partition only if expected prior root and active attempt match; conflict retains prior frontier. |

## Реальный join

The conditional_frontier_commit output (persisted expected-root/attempt-fenced cursor and receipt-before-frontier result) is reconciled by the fresh ingestion-progress/artifact reader and LIF-09 composition. CAP02 capture receipt/root and OPS profile remain their owners; missing continuity stays partial/historical.

**Outputs:** [LIF-03.conditional_frontier_commit](../cards/LIF-03/conditional_frontier_commit.md).

**Fresh consumer / ответственный контур:** Fresh cursor/progress reader, CAP artifact consumer, and LIF-09.vertical_witnesses/final_join_receipt for the selected receipt.

**Review размера:** 1 coherent result. Pattern pass P01/P02/P29/P32/P37/P38; behavioral stale-writer and 304-removal evidence required.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Shared acceptance, companions and rollback precedence.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **binding** — R19 status/navigation.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Writer rule/ref.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **binding** — Input rule.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:cursor-store`, `resource:cursor/{connector}/{partition}/{incarnation}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
