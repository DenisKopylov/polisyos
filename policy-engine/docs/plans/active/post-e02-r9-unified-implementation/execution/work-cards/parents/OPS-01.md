# OPS-01: родитель и соединение рабочих результатов

Canonical title: A0 source/profile commissioning and trust dossier. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-01).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-01.commissioning](../cards/OPS-01/commissioning.md) | [G09](../groups/G09.md) | Свежий runtime reader связывает exact build/config digest с фактическим effective profile и независимо назначенным trust generation; разрешение на выбранный source/use подтверждено или protected input удержан. |

## Реальный join

Existing RuntimeExecutionPolicyResolver produces a read-only effective-profile/build observation; OPS-01 binds the selected commissioning decision to that observation and persists its receipt. OPS-03 subsequently consumes this receipt to derive readiness/admission. OPS-01 does not wait for OPS-03 readiness and creates no second profile resolver.

**Outputs:** [OPS-01.commissioning](../cards/OPS-01/commissioning.md).

**Fresh consumer / ответственный контур:** Existing deployment release/commissioning reader, then OPS-02 or the selected protected source-use consumer.

**Review размера:** One receipt is retained because the result is a coherent commissioning decision; its profile, trust, grant, audience and service-owner inputs are not collapsed into one authority. Exact write paths and trust-record overlap remain unresolved until E02 rebind.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
