# GYD-29.candidate-census — Пересчитать полный candidate-positive denominator

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-29](../../parents/GYD-29.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every current source-derived candidate-positive row has complete file-type denominator, all eight dispositions, cited findings, frozen P37 provenance and false-exclusion review; historical 406 is not a cap.

**Предпочтительное решение.** Wire or extend the existing census/firewall owners and complete current source set; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-29's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing census/firewall owners and complete current source set.

**Входы.** current source/file set; historic 406 baseline; candidate rule/firewall and review criteria

**Выход и consumer.** Versioned full census/disposition receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh row/time consumer. P35 needs complete denominator; P36 cites findings; P37 freezes predicate provenance; P38 names measured property vs proxy.

**Positive.** Every current row resolves or inventory explicitly remains incomplete.

**Distinguishing negative.** Omitted firewall row, false exclusion or partial traversal cannot report zero/green.

**Matched removal.** Remove source row or P37 predicate with count marker retained; recomputed set fails.

**Граница контекста.** P35 needs complete denominator; P36 cites findings; P37 freezes predicate provenance; P38 names measured property vs proxy.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted current candidate-positive source/rule baseline consumed to derive full census.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-29`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Build complete current candidate-positive set/file denominator, reconcile historic 406, and populate row source/producer/path dispositions.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **execute** — Classify every deciding predicate under P37; omission/false exclusion must fail.
  `solution.implementation_steps[3]`
- **binding** — Rows follow source set, rules require owner/version/firewall and full traversal failure stays not_established.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **execute** — All eight dispositions and false-exclusion review; unreviewed/false-excluded rows keep census incomplete or widen mechanism under P40.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
