# GYD-29.time-roles — Разрешить S12 refs и разные time roles

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [GYD-29](../../parents/GYD-29.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every row distinguishes act, observation, publication, receipt and knowledge/as-of time; content refs resolve and stale refs emit downgrade/repair obligation.

**Предпочтительное решение.** Wire or extend the existing native time-role and S12 dereference owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-29's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing native time-role and S12 dereference owners.

**Входы.** candidate-census row/ref set; source-declared temporal role/effective time; currentness evidence

**Выход и consumer.** Append-only time/ref resolution and downgrade receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh time-aware consumer. No arrival-order or timestamp-proximity authority.

**Positive.** Distinct roles and current refs resolve from source evidence.

**Distinguishing negative.** Fresh timestamp cannot replace missing role; stale ref limits claim.

**Matched removal.** Remove source role/ref but keep prose marker; reader fails or downgrades.

**Граница контекста.** No arrival-order or timestamp-proximity authority.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Composition output (не start gate) [GYD-29.candidate-census](../../cards/GYD-29/candidate-census.md) | Consume only for the exact composition described here: Fresh consumer: fresh time-aware consumer. No arrival-order or timestamp-proximity authority. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-29`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **join** — Question requires distinct act/observation/publication/receipt/knowledge roles, ambiguous-timestamp adversary and source-role removal; one reader resolves all clauses.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **execute** — Resolve content refs/time roles and emit downgrade/repair obligation for stale refs.
  `solution.implementation_steps[2]`
- **execute** — One source-derived reader reconciles act, observation, publication, receipt, and knowledge times; an ambiguous timestamp or prose marker cannot supply a role.
  `task.r19_extension.question_slices[0]` (`R18-D02-Q03`); `task.r19_extension.question_ids[0]` (`R18-D02-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
