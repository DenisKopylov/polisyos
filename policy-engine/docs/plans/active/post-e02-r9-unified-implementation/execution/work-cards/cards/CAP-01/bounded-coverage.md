# CAP-01.bounded-coverage — Measure claim-scoped search coverage and no-hit

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [CAP-01](../../parents/CAP-01.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A no-hit supports only the source/routes/languages/cut whose known-item coverage was measured.

**Предпочтительное решение.** At the selected caller, derive the search denominator from admitted source contracts and registered routes, then persist a no-hit/coverage receipt scoped to route, language, cut and known exclusions; do not claim completeness for unsearched or inaccessible sources. Reuse SemanticDatasetCatalog and the existing acquisition planner/connector registry, not a parallel search inventory. Anchors: fabric/catalog/discovery.py:SemanticDatasetCatalog.search/resolve; runtime/quality/acquisition_planner.py:plan_evidence_acquisition.

**Граница владельца.** Catalog/discovery owner produces coverage receipt; CNT-08 consumes its claim limitation. Parent native lease family: `write:acquisition-action`, `write:source-catalog`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Frozen source/query/cut and diverse known items across the selected route/language set.

**Выход и consumer.** Persisted relative-recall/coverage and scoped no-hit receipt.

**Что можно готовить независимо.** Agree the route denominator and known-item set; do not require a global index.

**Где результат соединяется с другими.** Attach coverage to the candidate/no-hit receipt and have a fresh CNT-08 consumer limit broad absence when incomplete.

**Positive.** Known items are found across declared routes and the receipt reproduces its scoped result.

**Distinguishing negative.** Withheld seed, route, or language converts broad absence to limited.

**Matched removal.** Keep a green marker but remove cut/indexability binding; CNT-08 refuses broad absence.

**Граница контекста.** Three distinct predicates share a route but need separate contexts: candidate resolution, pre-egress query authority, and claim-scoped coverage/no-hit. The R19 coverage questions are a measurement artifact, not extra prose around discovery. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source/caller and source denominator are consumed for rebind; preparation may precede and original P0 remains stage gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-01.candidate-resolution](../../cards/CAP-01/candidate-resolution.md) | For the exact selected source/routes/selector whose coverage is claimed. |
| Composition output (не start gate) [CAP-01.query-disclosure](../../cards/CAP-01/query-disclosure.md) | Only for provider queries contributing to the coverage claim; local permitted corpus routes use their own evidence. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Measure source/routes/languages/cut and known-item no-hit; U035 is D03-Q01 search adequacy and U053 allows only an admitted no-hit query.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
