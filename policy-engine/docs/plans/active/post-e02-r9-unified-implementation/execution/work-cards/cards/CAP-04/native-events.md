# CAP-04.native-events — Persist source-qualified change and rights events

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [CAP-04](../../parents/CAP-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only an authenticated, source-scoped event can state a source change with its own position and time roles.

**Предпочтительное решение.** Add only a source-owner-adjacent CAP-04 adapter for a selected source-native event/correction, bind event identity, exact old/new root/relation, source generation, verifier and time roles, then hand it to ClaimDependencyFieldRegistry/ClaimLedgerOwnerPort and the existing epoch_validity_cascade/DecisionValidityService. CAP-04 emits qualified source evidence; LIF-02 alone replays and fences currentness. Anchors: scientist/evidence/claims/head_index.py; runtime/quality/epoch_validity_cascade.py; scientist/validation/decision_validity.py.

**Граница владельца.** CAP-04 adapter adjacent to accountable source owner; LIF-02 remains canonical consumer. Parent native lease family: `write:source-event-adapter/{owner}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Verified source/custodian event, source incarnation/position, exact old/new root or relation, scope, effective and observed times.

**Выход и consumer.** Persisted event receipt with coverage and source lineage.

**Что можно готовить независимо.** Select a real source event contract and native verifier; a supplied assertion remains typed candidate until admitted.

**Где результат соединяется с другими.** LIF-02 replays accepted event against enrolled dependencies; CAP-04 does not schedule/cascade.

**Positive.** A qualified correction/retraction reaches only enrolled dependents and triggers fresh recomputation.

**Distinguishing negative.** Backdated event, empty inbox, duplicate/reset position or unrelated source does not establish broad currentness.

**Matched removal.** Drop source identity/position binding but retain event marker; stale-head consumer refuses.

**Граница контекста.** Source-supplied change events, measured observation cuts, and LIF-02 currentness are different evidence/authority contexts. Keeping them together risks treating a heartbeat/empty feed as a source event or giving CAP-04 a second cascade. R19 operational/incident records stay typed apart from legal events, causal assessments, and source-supplied events. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted selected owner/path consumed when resolved; original stage gate remains.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:owner_readiness`: Consume exact root/relation only for source event or observed content binding.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Qualified source/custodian events bind source position, correction lineage, scope/coverage and verifier; new event kinds need typed owner, not CAP adjudication.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.product_verification`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[8]`; `task.r19_extension.question_slices[9]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[8]`; `solution.preferred_solution`; `solution.implementation_steps[1]`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[1]`; `solution.deviation_triggers[1]`
- **binding** — Q12 late corrections preserve source/effective/known time roles; local observation order is not external order.
  `task.r17_extension.quality_cases[3]`
- **binding — subclause:** Do not infer enrollment from positive references or verified events from URL changes.; source `task.migration`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
