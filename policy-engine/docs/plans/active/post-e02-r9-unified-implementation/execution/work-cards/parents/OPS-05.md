# OPS-05: родитель и соединение рабочих результатов

Canonical title: Control-store migrations and cross-store recovery. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-05).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-05.schema-directions](../cards/OPS-05/schema-directions.md) | [G09](../groups/G09.md) | Every selected reader/writer/schema/rule direction can consume the actual persisted representation before rollout or rollback; an unsupported direction is refused. |
| [OPS-05.restore-cut](../cards/OPS-05/restore-cut.md) | [G09](../groups/G09.md) | A selected restored scope reaches fresh protected read only after DB/control/CAS state, required history, rights and the continuity witness outside the actual rollback closure reconcile, with a fence against intervening changes. |
| [OPS-05.retained-uses](../cards/OPS-05/retained-uses.md) | [G09](../groups/G09.md) | For a selected use, only the exact required retained payload or qualified retained result with current rights and sufficient basis is available; lawfully erased raw dependencies stay unavailable. |
| [OPS-05.byte-release](../cards/OPS-05/byte-release.md) | [G09](../groups/G09.md) | The object/version verified for integrity is the object/version actually consumed, and integrity-dependent release waits for its required verification boundary. |

## Реальный join

Join schema-direction receipts, selected quarantine restore-cut, per-use retained-representation result and actual-byte reader/sink proof. On a selected current/protected restore, the existing claim/publication owner and fresh restored-scope reader require LIF-02 material history plus LIF-05 rights and a continuity witness outside the actual rollback closure; otherwise retain scoped historical/limited status.

**Outputs:** [OPS-05.schema-directions](../cards/OPS-05/schema-directions.md), [OPS-05.restore-cut](../cards/OPS-05/restore-cut.md), [OPS-05.retained-uses](../cards/OPS-05/retained-uses.md), [OPS-05.byte-release](../cards/OPS-05/byte-release.md).

**Fresh consumer / ответственный контур:** Existing ControlPlaneStore migration/read path, replay-or-restore owner, canonical CAS reader and sink; fresh authorized claim/publication reader for a restored selected scope.

**Review размера:** Four independently falsifiable properties replace the overloaded restore row. The 9 acceptance units are not separate writers: U012/U013/U014/U015 route to their semantic property; cross-card task deliverable/rollback and mandatory companions stay at parent composition. Existing DB, CAS, rights and claim owners remain intact; exact lease overlaps are re-resolved after E02.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate acceptance, coordination, or shared constraint across schema-directions, restore-cut, retained-uses, byte-release; selectors task.deliverable, task.positive, task.adversarial, task.removal, task.surface, task.rollback, task.migration, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[8], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.rollback_precedence, task.r17_extension.requirement, task.r17_extension.positive, task.r17_extension.adversarial, task.r17_extension.removal, task.r17_extension.product_verification, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.preferred_solution, solution.free_grow.data_or_config_growth, solution.migration_and_rollback, solution.acceptance_discriminators[0], solution.input_resolution_rule are reconciled by parent_join against the named card outputs and existing consumer, not implemented as peer-owner work.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[8]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.free_grow.data_or_config_growth`; `solution.migration_and_rollback`; `solution.acceptance_discriminators[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:control-schema-migration`, `resource:control/{cell}/backup-restore`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
