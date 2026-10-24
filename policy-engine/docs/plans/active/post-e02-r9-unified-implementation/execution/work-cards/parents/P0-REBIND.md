# P0-REBIND: родитель и соединение рабочих результатов

Canonical title: Reconcile source, obligations, ownership and lease map. R26 форма: `coordination`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/12-execution.md#P0-REBIND).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [P0-REBIND.original-set-reconciliation](../cards/P0-REBIND/original-set-reconciliation.md) | [G00](../groups/G00.md) | Every original predicate and accepted-E02 delta has one current disposition, native owner, actual consumer/generated/test/API closure, conditional facets, stage and lease; scoped releases never imply global completion. |

## Реальный join

original-set-reconciliation emits Append-only per-original-predicate disposition and owner/consumer closure map, with unresolved rows retained and bounded scoped release evidence.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to FINAL-FREEZE coordinator consuming global completed reconciliation; scoped release alone is not global completion.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [P0-REBIND.original-set-reconciliation](../cards/P0-REBIND/original-set-reconciliation.md).

**Fresh consumer / ответственный контур:** FINAL-FREEZE coordinator consuming global completed reconciliation; scoped release alone is not global completion.

**Review размера:** Root preserves the full original inventory, historical dispositions, accepted-E02 delta, owner/read/generated/test/API closure, selected conditions, stage and leases in one journal.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.


## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
