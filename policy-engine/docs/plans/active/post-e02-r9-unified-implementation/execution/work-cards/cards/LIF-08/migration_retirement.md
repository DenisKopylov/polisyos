# LIF-08.migration_retirement — Завершить migration до retire

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-08](../../parents/LIF-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Old/new roots coexist; retire only after refs/backup/GC reconcile.

**Предпочтительное решение.** Extend existing catalog rollout; consume OPS trust/backup and source/reader matrix.

**Граница владельца.** CAP/OPS/LIF05/LIF02 keep owners.

**Входы.** CAP02 selected second-source receipt/cut; LIF08 directional matrix and old/new reader generation; LIF07 actual influence/descendant closure for selected derived uses; OPS trust/restore profile, GC roots and LIF05 rights.

**Выход и consumer.** Migration roots/retirement read by old/new consumers.

**Что можно готовить независимо.** Inventory and compatible-reader/retirement preparation may proceed against agreed interfaces; actual receipt, matrix, influence, rights and restore results join before retirement.

**Где результат соединяется с другими.** Retirement reader composes actual selected source receipt, reader matrix, influence/rights and OPS restore/GC roots; compatible preparation may proceed independently.

**Positive.** New reader sees real artifact; old remains within validity.

**Distinguishing negative.** Stale offline reader or dropped backup root.

**Matched removal.** Remove generation/GC check; old reader remains green.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:owner_readiness`: Consume selected reader/API and retirement.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-07](../../parents/LIF-07.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-08.directional_semantics](../../cards/LIF-08/directional_semantics.md) | Only for selected migration readers whose compatible old/new matrix and requiredness are part of the retirement condition. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Rollback/parallel roots/retire.
  `task.rollback`; `task.migration`
- **execute** — Fresh reader and GC-safe parallel roots.
  `solution.implementation_steps[5]`
- **execute** — Promotion/rollback distinct roots.
  `solution.migration_and_rollback`
- **binding** — OPS trust/backup.
  `solution.composition_contracts[1]`
- **binding** — OPS profile.
  `solution.inputs_to_resolve[1]`

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — Conditional consumer: only a selected migration whose old/new reader compatibility depends on same-meaning SourceContract growth versus an adapter for new meaning; compatible preparation alone is not a retirement gate. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[1]` — Conditional consumer: selected retirement consumes the directional compatibility/reader-generation result for the old/new reader matrix before dropping old roots. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Conditional consumer: selected migration consumes the bound source receipt and directional matrix when reconciling old/new roots, refs, backups and GC. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
