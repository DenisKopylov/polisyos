# DEB-03: родитель и соединение рабочих результатов

Canonical title: Public/private boundary and release inventory. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-03).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-03.private-reachability](../cards/DEB-03/private-reachability.md) | [G10](../groups/G10.md) | Every production cross-module private import, function-local import and private-attribute edge is routed through an owner-approved supported boundary or retained as an explicit unresolved dynamic limitation. |
| [DEB-03.release-inventory](../cards/DEB-03/release-inventory.md) | [G08](../groups/G08.md) | For each originally named release fragment, public-break inventory matches current generated API/source delta and a content-bound competent owner review. |

## Реальный join

private-reachability emits Recomputed private-reach inventory with explicit reviewed boundary or bounded unresolved dynamic case.; release-inventory emits Versioned per-fragment break inventory and bound review receipt consumed at release admission.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh check_package_import_gates.py/architecture import consumer and release promotion/public-surface review consumer.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-03.private-reachability](../cards/DEB-03/private-reachability.md), [DEB-03.release-inventory](../cards/DEB-03/release-inventory.md).

**Fresh consumer / ответственный контур:** Fresh check_package_import_gates.py plus tests/repo_quality/architecture public-surface snapshot/promotion consumer, each consuming its own reach or release-inventory result.

**Review размера:** Private-name reachability and public-release-fragment inventory are independent; neither closes the other.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This fragment is a shared acceptance/boundary clause for both private reach and release inventory; parent_join requires both actual outputs without substituting one for the other.
  `task.deliverable`; `task.positive`; `task.removal`; `task.surface`; `task.rollback`; `solution.preferred_solution`
- **binding** — This fragment is a shared acceptance/boundary clause for both private reach and release inventory; parent_join requires both actual outputs without substituting one for the other.
  `task.migration`; `solution.migration_and_rollback`; `solution.composition_contracts[2]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
