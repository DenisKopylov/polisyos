# GYD-22.demand-abstention — T6: измерить demand-pull/abstention

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-22](../../parents/GYD-22.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Canonical T6 demand-pull and abstention measures preserve their owner denominators and DES-10 false-abstention diagnostics.

**Предпочтительное решение.** Wire or extend the existing G8 T6 owner and DES-10 diagnostic producer; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-22's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing G8 T6 owner and DES-10 diagnostic producer.

**Входы.** T6 definitions and source snapshots; identity-matched V2/V3 runs

**Выход и consumer.** T6 separate measure/missingness receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: existing G8 Cycle Board. No promotion objective or combined scalar.

**Positive.** Demand and abstention remain separately visible.

**Distinguishing negative.** False abstention or missing basis cannot be hidden in useful_design_rate.

**Matched removal.** Remove a measurement; board reports missing/not_established.

**Граница контекста.** No promotion objective or combined scalar.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../../cards/GYD-17/evidence-readback.md) | `direct:interface_agreement; acceptance:composition`: Each signal card consumes identity-matched V2 production-run evidence.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [GYD-18.domain-distribution](../../cards/GYD-18/domain-distribution.md) | `direct:interface_agreement; acceptance:composition`: Each signal card consumes identity-matched V3 strata/distribution evidence.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[2]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-22`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.



### Обязанности внутри составных fragments

- `solution.preferred_solution` — Map T6 demand-pull/abstention to its canonical owner, definition, window, denominator and fully named label. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `solution.implementation_steps[1]` — Compute/read the T6 demand-pull/abstention signal from identity-matched persisted runs through its native owner. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `solution.implementation_steps[2]` — Report T6 demand-pull/abstention value, denominator, missingness, source hash and uncertainty without zero-filling or invented thresholds. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — Provide the T6 demand-pull and abstention measures with DES-10 false-abstention diagnostics. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
