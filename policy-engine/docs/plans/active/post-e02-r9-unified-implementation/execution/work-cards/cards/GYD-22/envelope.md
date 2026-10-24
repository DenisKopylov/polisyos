# GYD-22.envelope — T1: измерить envelope expansion

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-22](../../parents/GYD-22.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Canonical T1 source/window/denominator and matching V2/V3 run produce an explicit envelope-expansion value or missingness.

**Предпочтительное решение.** Wire or extend the existing G8 T1 metric owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-22's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing G8 T1 metric owner.

**Входы.** T1 definition/snapshot; identity-matched V2/V3 runs

**Выход и consumer.** T1 value/denominator/window/source hash/uncertainty

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: existing G8 Cycle Board. Descriptive measure only.

**Positive.** Value is source-bound and readable with uncertainty.

**Distinguishing negative.** Missing definition/run is not zero or a causal conclusion.

**Matched removal.** Remove T1 measurement; board reports missing/not_established.

**Граница контекста.** Descriptive measure only.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../../cards/GYD-17/evidence-readback.md) | `direct:interface_agreement; acceptance:composition`: Each signal card consumes identity-matched V2 production-run evidence.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [GYD-18.domain-distribution](../../cards/GYD-18/domain-distribution.md) | `direct:interface_agreement; acceptance:composition`: Each signal card consumes identity-matched V3 strata/distribution evidence.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-22`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **secondary_signal_owner — subclause:** Map T1 envelope expansion to its canonical owner, definition, window, denominator and fully named label.; source `solution.preferred_solution`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_signal_owner — subclause:** Compute/read the T1 envelope expansion signal from identity-matched persisted runs through its native owner.; source `solution.implementation_steps[1]`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **secondary_signal_owner — subclause:** Report T1 envelope expansion value, denominator, missingness, source hash and uncertainty without zero-filling or invented thresholds.; source `solution.implementation_steps[2]`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
