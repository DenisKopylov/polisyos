# OPS-04: родитель и соединение рабочих результатов

Canonical title: Supervised external worker composition. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-04).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-04.external-runner](../cards/OPS-04/external-runner.md) | [G09](../groups/G09.md) | An authorized durable job claimed by the supervised process has one valid existing lease generation and a fresh API reader observes persisted outcome; an effect without receipt stays unknown. |

## Реальный join

One supervised entrypoint emits lifecycle facts into the existing ControlPlaneStore/ControlWorker path, which OPS-03 projects and the fresh authorized API reader consumes. OPS-05 joins actual direction only when the selected profile rolls components independently; LIF-04 remains effect/duty owner.

**Outputs:** [OPS-04.external-runner](../cards/OPS-04/external-runner.md).

**Fresh consumer / ответственный контур:** Existing ControlWorker/ControlPlaneStore lease path and fresh API result reader; OPS-03 readiness consumer; selected OPS-05 compatibility reader.

**Review размера:** One runner integration is coherent across lifecycle checkpoints. The runner does not own effect reconciliation, application retry policy or schema compatibility, and its exact path lease remains unresolved until accepted-source rebind.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:external-runner-entrypoint`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
