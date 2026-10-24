# GYD-05: родитель и соединение рабочих результатов

Canonical title: S3 source-backed legal-subject membership. R26 форма: `retain`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/04-gy-core.md#GYD-05).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [GYD-05.legal-membership](../cards/GYD-05/legal-membership.md) | [G02](../groups/G02.md) | Purpose-, subject-, jurisdiction-, context- and time-scoped legal membership is recomputed from an independent CORR-B1 source, while authority changes only after a competent ruling is admitted. |

## Реальный join

Join the independent scoped membership source and competent ruling at the existing legal-correspondence consumer. The fresh result may compare legal membership; authority remains not_established until the external ruling is admitted. Keep legal identity separate from any causal cohort or policy effect. Task-level source pins, dispatch condition, stage override, conditional acceptance, completion planes and canonical lease keys remain inherited from the original parent records; these child routes do not replace them.

**Outputs:** [GYD-05.legal-membership](../cards/GYD-05/legal-membership.md).

**Fresh consumer / ответственный контур:** Fresh src/polisyos/foundry/validation/legal_correspondence.py::LegalCorrespondenceResult readback.

**Review размера:** R25 retain: one scoped membership claim jointly depends on source and ruling, which remain distinct evidence inputs and signatures.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
