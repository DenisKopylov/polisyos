# CAP-04.currentness-join — Compose event receipt into fenced fresh projection

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [CAP-04](../../parents/CAP-04.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An enrolled claim is green only after replay and publication fencing cover its source dependency cut.

**Предпочтительное решение.** Enroll the selected dependency denominator and replay qualified event/observation cuts through the existing ClaimLedger/epoch-validity and DecisionValidityService owners; fence publication/current-use at the fresh reader and project affected plus unaffected results through UI-19. No scheduler or second cascade is required for a fresh authority read to refuse stale green. Anchors: scientist/evidence/claims/head_index.py:ClaimDependencyFieldRegistry/ClaimLedgerOwnerPort; runtime/quality/epoch_validity_cascade.py:epoch_validity_cascade; scientist/validation/decision_validity.py:DecisionValidityService.

**Граница владельца.** Existing LIF-02/Claim Ledger/Decision Validity/publisher owners; UI-19 projects the result. Parent native lease family: `write:source-event-adapter/{owner}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Accepted CAP-04 event/observation receipt, enrollment denominator, source cut and current claim generation.

**Выход и consumer.** Persisted fresh/limited/blocked projection consumed by the selected reader and currentness surface.

**Что можно готовить независимо.** Pin the existing LIF-02 interface and the affected source/claim set.

**Где результат соединяется с другими.** Join event-before-enrollment replay, expected-head reconciliation, and publication fence at the real consumer.

**Positive.** Late and pre-enrollment events replay to the correct fresh affected claim; unrelated claims remain intact.

**Distinguishing negative.** Missing journal, stale index, rights race, scheduler-off read or late completion cannot leave unjustified green.

**Matched removal.** Remove dependency/generation binding but keep current marker; fresh consumer refuses green.

**Граница контекста.** Source-supplied change events, measured observation cuts, and LIF-02 currentness are different evidence/authority contexts. Keeping them together risks treating a heartbeat/empty feed as a source event or giving CAP-04 a second cascade. R19 operational/incident records stay typed apart from legal events, causal assessments, and source-supplied events. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted selected owner/path consumed when resolved; original stage gate remains.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:interface_agreement; conditional_acceptance_requirements:composition`: Consume enrollment/replay/generation/publication interface at currentness consumer only.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; CAP-04 claims delivered source change has affected current-use or public-claim status |
| Supplier [UI-19.claim-currentness](../../cards/UI-19/claim-currentness.md) | `acceptance:composition`: For CAP-04 acceptance that projects current-use/public-claim status, UI-19 consumes the actual LIF-02 fresh projection for affected and unaffected claims. This is the existing surface companion, not a CAP writer or a new stage gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-04.native-events](../../cards/CAP-04/native-events.md) | Selected native source-event route with actual source cut/position; not required for qualified no-feed observation route. |
| Composition output (не start gate) [CAP-04.bounded-observation](../../cards/CAP-04/bounded-observation.md) | Selected bounded observation route; does not assert native event continuity and is not a universal second input to event replay. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — LIF-02 alone owns enrollment/replay/generation/publication fence and fresh claim currentness; CAP supplies qualified event or observation only.
  `task.migration`; `task.currentness_surface_delivery.canonical_task`; `task.currentness_surface_delivery.supplier`; `task.currentness_surface_delivery.required_property`; `task.currentness_surface_delivery.acceptance`; `task.refusal_seam_rule`; `task.r19_extension.question_slices[7]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **binding** — Q08 requires a cumulative anchor against the last accepted basis and separates benign drift from actual effect loss/late labels at currentness; LIF-07/DES-04/GYD owners retain those semantics.
  `task.r17_extension.quality_cases[1]`
- **execute — subclause:** An enrolled material change invalidates dependent current projection while unrelated source remains valid; fresh consumer recomputes status.; source `task.positive`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **execute — subclause:** Late/backdated events, enrollment gaps, missing journal, stale index, rights race or scheduler-off read cannot preserve unjustified green.; source `task.adversarial`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **execute — subclause:** Removing dependency/generation binding while retaining event/current markers makes the fresh consumer refuse green.; source `task.removal`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **binding — subclause:** Keep the D16 worker lease/due clock distinct from source position and OPS-11 duties.; source `task.r19_extension.question_ids[4]`. Primary fragment route stays unchanged; this identifies the owned sub-result.
- **binding — subclause:** Qualified events or observations hand to LIF-02 enrollment, replay, generation and publication-currentness fencing; CAP-04 does not create a cascade or scheduler.; source `solution.preferred_solution`. Primary fragment route stays unchanged; this identifies the owned sub-result.

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
