# DEB-13: родитель и соединение рабочих результатов

Canonical title: Commission numeric VOI granularity and its decision/ranking basis. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-13).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-13.ds15-numeric-voi](../cards/DEB-13/ds15-numeric-voi.md) | [G05](../groups/G05.md) | A versioned source-bound numeric-VOI result reaches a fresh DS15/UI-17 consumer under explicit refusal when its supported basis is absent; gross EVSI is independent of cost. |

## Реальный join

ds15-numeric-voi emits Versioned gross EVSI or cost-bound net/ENBS artifact with provenance/refusal, consumed by fresh route/UI projection.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh DS15/UI-17 selected-route consumer; CAP-03 cost read is conditional for net/ENBS/cost-sensitive use.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-13.ds15-numeric-voi](../cards/DEB-13/ds15-numeric-voi.md).

**Fresh consumer / ответственный контур:** Fresh DS15/UI-17 selected-route consumer; CAP-03 cost read is conditional for net/ENBS/cost-sensitive use.

**Review размера:** Keep metric owner/oracle -> versioned producer/artifact -> fresh DS15/UI-17 consumer in one numeric-VOI vertical.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`, `write:semantic-owner/voi-metric`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
