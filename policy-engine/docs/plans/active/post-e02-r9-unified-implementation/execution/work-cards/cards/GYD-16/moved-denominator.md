# GYD-16.moved-denominator — Пересчитать полный moved-row denominator

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-16](../../parents/GYD-16.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Полный принятый source-derived набор GY-acted obligation/path rows и file-type denominator, с source path/hash и disputed-row owner reconciliation.

**Предпочтительное решение.** Wire or extend the existing Native capability coverage checker and canonical task/capability source owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-16's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Native capability coverage checker and canonical task/capability source owners.

**Входы.** accepted E02 task/capability mapping; source path/hash and file-type denominator

**Выход и consumer.** Moved-row denominator receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh row-to-chain matrix reader. This card derives the source set only; it does not assign capability ownership or rewrite §8.5 history.

**Positive.** Removing or adding one canonical source row changes the recomputed denominator.

**Distinguishing negative.** A declared table count or sampled source set cannot stand in for the accepted source denominator.

**Matched removal.** Delete a source row while preserving matrix markers; recomputation disagrees.

**Граница контекста.** This card derives the source set only; it does not assign capability ownership or rewrite §8.5 history.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted GY source mapping consumed to derive complete moved-row and file-type denominator.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-16`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Derive complete accepted source set, file-type denominator and disputed-row resolution.
  `solution.implementation_steps[0]`
- **binding** — New obligations enter the canonical source and are recomputed into this same denominator.
  `solution.free_grow.data_or_config_growth`
- **binding** — Bounded full inventory behavior and missing-member disposition belong to denominator recomputation.
  `solution.free_grow.resource_behavior`
- **binding** — Accepted source/full denominator and the source input-resolution classification define this card; internal producer gaps are assigned work.
  `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
