# GYD-22.recall-staleness — T7: проверить known-seed recall/index freshness

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-22](../../parents/GYD-22.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Known-seed miss and stale-index evidence support only the existing search-ceiling interpretation.

**Предпочтительное решение.** Wire or extend the existing Canonical search corpus/index and T7 owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-22's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Canonical search corpus/index and T7 owner.

**Входы.** known-seed corpus; index freshness evidence; matched V2/V3 search runs

**Выход и consumer.** Recall/staleness witness plus T7 measure

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: existing G8 Cycle Board and search reader. No new gate or domain attribution.

**Positive.** Known seed and current index are evidenced at the actual reader.

**Distinguishing negative.** Stale index/missed known seed prevents no-ceiling interpretation.

**Matched removal.** Remove seed or freshness evidence while keeping marker; T7 becomes limited.

**Граница контекста.** No new gate or domain attribution.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../../cards/GYD-17/evidence-readback.md) | `direct:interface_agreement; acceptance:composition`: Each signal card consumes identity-matched V2 production-run evidence.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [GYD-18.domain-distribution](../../cards/GYD-18/domain-distribution.md) | `direct:interface_agreement; acceptance:composition`: Each signal card consumes identity-matched V3 strata/distribution evidence.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[2]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-22`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Known-seed miss and stale-index case belong only to T7.
  `solution.implementation_steps[3]`

### Обязанности внутри составных fragments

- `solution.preferred_solution` — Map T7 search recall/index staleness to its canonical owner, definition, window, denominator and fully named label. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `solution.implementation_steps[1]` — Compute/read the T7 search recall/index staleness signal from identity-matched persisted runs through its native owner. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `solution.implementation_steps[2]` — Report T7 search recall/index staleness value, denominator, missingness, source hash and uncertainty without zero-filling or invented thresholds. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — Provide the T7 known-seed recall and index-freshness witness; it supports only the existing search-ceiling interpretation. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
