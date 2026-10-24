# CAP-04.bounded-observation — Record change only within an observed source cut

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [CAP-04](../../parents/CAP-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Snapshot comparison supports only measured selector/profile/coverage and cannot claim source continuity between polls.

**Предпочтительное решение.** For a selected source without a feed, compare complete permitted CAP-02 observations through its existing capture/decoder path and persist exact old/new representations, selector/profile, coverage, observation interval and expected local head. Hand only that measured cut to LIF-02 bounded-observation; do not invent source-effective time, between-poll continuity or removals. Anchors: fabric/connectors/sources/http_base.py:RawHTTPResponseObserver; scientist/evidence/claims/head_index.py:ClaimDependencyDenominatorReceipt; scientist/validation/decision_validity.py.

**Граница владельца.** CAP-02 permitted observation plus source-specific CAP-04 observation journal. Parent native lease family: `write:source-event-adapter/{owner}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Comparable permitted old/new representations, exact selector/profile, acquisition interval, coverage and known-at time.

**Выход и consumer.** Persisted observed-change/no-change receipt with bounded cut and exclusions.

**Что можно готовить независимо.** The source may lack a native event feed; CAP-02 supplies permitted comparable observations.

**Где результат соединяется с другими.** Join LIF-02's bounded-observation branch; local journal order never becomes external effective-time order.

**Positive.** Observed material change invalidates matching claims while unrelated claims retain currentness.

**Distinguishing negative.** Missed transient, omitted partition, access failure, empty feed, or heartbeat cannot prove unchanged.

**Matched removal.** Remove coverage/cut binding but retain poll-success marker; fresh consumer limits the no-change claim.

**Граница контекста.** Source-supplied change events, measured observation cuts, and LIF-02 currentness are different evidence/authority contexts. Keeping them together risks treating a heartbeat/empty feed as a source event or giving CAP-04 a second cascade. R19 operational/incident records stay typed apart from legal events, causal assessments, and source-supplied events. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted selected owner/path consumed when resolved; original stage gate remains.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:owner_readiness`: Consume exact root/relation only for source event or observed content binding.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Silent-source Q07, support drift, exact cut/coverage, overlapping poll head and delayed old poll are bounded observation evidence, never feed continuity.
  `task.acceptance_steps[4]`; `task.acceptance_steps[5]`; `task.r17_extension.quality_cases[0]`; `task.r19_extension.question_ids[0]`; `solution.implementation_steps[4]`; `solution.implementation_steps[5]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`; `solution.deviation_triggers[0]`
- **binding** — D3 is the bounded observation/reissue lane; local journal does not infer source continuity.
  `task.r17_extension.delivery_slices[0]`
- **binding — subclause:** For the snapshot-comparison route, CAP-02 supplies comparable permitted observations and CAP-04 persists exact observed old/new representations, selector/profile/coverage and acquisition times without inventing source-effective time or inter-poll completeness.; source `solution.preferred_solution`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
