# GYD-19.negative-matrix — Привязать исходные негативные cases a–v

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-19](../../parents/GYD-19.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each original V4 a–v case maps to actual owner/consumer, source predicate, precondition, typed expectation, path and deciding evidence.

**Предпочтительное решение.** Keep original V4 a–v list as authoritative indexed matrix; bind each to source predicate and actual owner/consumer before the final wave.

**Граница владельца.** Within GYD-19's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Owns the source-indexed case mapping only; product gates remain with native consumers.

**Входы.** Accepted E02 owner routes; Original a–v criteria; Permitted CAS/world/time/VOI/EvalSafety fixtures

**Выход и consumer.** Versioned case-to-owner/applicability matrix with command and expected typed outcome.

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: negative-battery runner reads the bound case matrix before executing owner commands.

**Positive.** All original clauses have resolvable real test paths.

**Distinguishing negative.** A case cannot be asserted inapplicable or replaced by a generated variant.

**Matched removal.** Remove one original case from source mapping; full denominator detects it.

**Граница контекста.** P34/P41 exclusion and inherited-red decisions are separate source dispositions; this card does not decide product gates.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted original V4 predicates/owner routes consumed to bind the authoritative a–v denominator.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-19`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind each letter to canonical consumer, predicate, precondition, typed expected outcome, path and evidence.
  `solution.implementation_steps[0]`
- **binding** — Accepted owner routes, permitted fixtures and source-input classification determine mapping; missing producer/bridge is assigned work.
  `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
