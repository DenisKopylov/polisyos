# OPS-02: родитель и соединение рабочих результатов

Canonical title: Finite local candidate pilot. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-02).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-02.local-candidate](../cards/OPS-02/local-candidate.md) | [G09](../groups/G09.md) | После restart свежий reader находит persisted quarantine receipt, отдельное admission result и разрешенный artifact; capture/status сами по себе не дают admissible read. |

## Реальный join

The pilot card emits its persisted receipt/admission/read evidence to a fresh acquisition consumer, and records conditional restore, rights, secret, spend and host-limit outcomes from OPS-05/06/07/08 and LIF-06. The first practical-use decision remains FINAL-USE.

**Outputs:** [OPS-02.local-candidate](../cards/OPS-02/local-candidate.md).

**Fresh consumer / ответственный контур:** Existing acquisition/job and admission path, with a fresh API/artifact reader after restart; an OPS-05 selected restore consumer only when restore is included.

**Review размера:** No code is presumed from the historical pin. One E2E card is retained because all steps make one candidate journey; commissioning, restore, spend, resource admission and actual use stay owned elsewhere and only join when their source conditions activate.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
