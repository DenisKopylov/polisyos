# OPS-03: родитель и соединение рабочих результатов

Canonical title: Effective posture and dependency readiness. R26 форма: `retain`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-03).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-03.profile-readiness](../cards/OPS-03/profile-readiness.md) | [G09](../groups/G09.md) | Для выбранной операции readiness становится green только когда все действительно обязательные live dependencies, schema and effective-profile checks are observed; liveness remains process viability. |

## Реальный join

OPS-03 emits a selected-profile readiness projection; root composes the true DB/CAS/worker or activated site/remote/offline evidence with the fresh route admission consumer. Liveness and LIF-02 claim currentness remain separate.

**Outputs:** [OPS-03.profile-readiness](../cards/OPS-03/profile-readiness.md).

**Fresh consumer / ответственный контур:** Existing `/ready` route and the worker-backed acquisition/admission consumer; safe operator payload is a secondary projection.

**Review размера:** One read projection, not a scheduler or global status lattice. Named owner signals and required components remain conditional on the selected profile; liveness stays distinct.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
