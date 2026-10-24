# GYD-10: родитель и соединение рабочих результатов

Canonical title: O2 exploratory FDR candidate controller. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/05-gy-learning.md#GYD-10).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [GYD-10.o2-fdr-candidate](../cards/GYD-10/o2-fdr-candidate.md) | [G03](../groups/G03.md) | A real, in-budget DDM signal is recomputed against the accepted FDR plan and complete stream history, then persisted only as candidate_unverified with spend and may_not_use_for. |

## Реальный join

Join the accepted plan, source-qualified DDM stream, complete denominator/look/dependence/state record, controller decision and persisted candidate at the fresh HypothesisLedger reader. The result remains candidate_unverified with may_not_use_for; O1 confirmation is a later separate consumer, never authority or an O2 write. Task-level source pins, dispatch condition, stage override, conditional acceptance, completion planes and canonical lease keys remain inherited from the original parent records; these child routes do not replace them.

**Outputs:** [GYD-10.o2-fdr-candidate](../cards/GYD-10/o2-fdr-candidate.md).

**Fresh consumer / ответственный контур:** Fresh src/polisyos/runtime/quality/hypothesis_ledger.py::HypothesisLedger readback after the canonical OnlineFDRController/DDM event flow.

**Review размера:** R25 sequence retained. Look/exposure, restart, memory and FDR validity belong to one tested online procedure; this card does not take O1 ownership or add a ledger.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
