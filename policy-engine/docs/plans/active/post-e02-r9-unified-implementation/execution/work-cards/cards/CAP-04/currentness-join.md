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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted selected owner/path consumed when resolved; original stage gate remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:interface_agreement; conditional_acceptance_requirements:composition`: Consume enrollment/replay/generation/publication interface at currentness consumer only.<br>Source: `task.depends_on[2]`; `task.conditional_acceptance_requirements[0]`.<br>Условия: original direct relation; source stage rules govern; CAP-04 claims delivered source change has affected current-use or public-claim status |
| Supplier [UI-19.claim-currentness](../../cards/UI-19/claim-currentness.md) | `acceptance:composition`: For CAP-04 acceptance that projects current-use/public-claim status, UI-19 consumes the actual LIF-02 fresh projection for affected and unaffected claims. This is the existing surface companion, not a CAP writer or a new stage gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-04.native-events](../../cards/CAP-04/native-events.md) | Selected native source-event route with actual source cut/position; not required for qualified no-feed observation route. |
| Composition output (не start gate) [CAP-04.bounded-observation](../../cards/CAP-04/bounded-observation.md) | Selected bounded observation route; does not assert native event continuity and is not a universal second input to event replay. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — LIF-02 alone owns enrollment/replay/generation/publication fence and fresh claim currentness; CAP supplies qualified event or observation only.
  `task.migration`; `task.currentness_surface_delivery.canonical_task`; `task.currentness_surface_delivery.supplier`; `task.currentness_surface_delivery.required_property`; `task.currentness_surface_delivery.acceptance`; `task.refusal_seam_rule`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **binding** — Q08 requires a cumulative anchor against the last accepted basis and separates benign drift from actual effect loss/late labels at currentness; LIF-07/DES-04/GYD owners retain those semantics.
  `task.r17_extension.quality_cases[1]`
- **execute** — Current route matches for source identity/position and currentness replay. U073 is an additional binding clause for this same question, but coverage currently selects `question_ids[4]`; bind U073 to R18-D16-Q02 by value because question_ids and question_slices have different orderings.
  `task.r19_extension.question_slices[7]` (`R18-D16-Q02`); `task.r19_extension.question_ids[4]` (`R18-D16-Q02`)

### Обязанности внутри составных fragments

- `task.positive` — An enrolled material change invalidates dependent current projection while unrelated source remains valid; fresh consumer recomputes status. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.adversarial` — Late/backdated events, enrollment gaps, missing journal, stale index, rights race or scheduler-off read cannot preserve unjustified green. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.removal` — Removing dependency/generation binding while retaining event/current markers makes the fresh consumer refuse green. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_ids[4]` — Keep the D16 worker lease/due clock distinct from source position and OPS-11 duties. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `solution.preferred_solution` — Qualified events or observations hand to LIF-02 enrollment, replay, generation and publication-currentness fencing; CAP-04 does not create a cascade or scheduler. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — Consume the qualified late correction through LIF-02 enrollment/replay and publication fencing; affected claims refresh and unrelated claims remain intact. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[1]` — Route a genuine qualified correction/retraction to enrolled dependents through LIF-02; the metrics-only path remains its own claim re-evaluation. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Only when the record is selected and qualified as a bounded observation cut, let LIF-02 re-evaluate the matching enrolled feasibility predicate; do not promote the operational record to a source event. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — When that source event or a separately qualified bounded observation is selected, carry only its supported delta to the enrolled feasibility claim through LIF-02 replay/fencing. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Consume the real correction at LIF-02 with its source/scope and dependency binding so only enrolled claims are recomputed. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[8]` — Deliver the qualified shutdown event to LIF-02 so only affected enrolled current uses are fenced and recomputed. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[9]` — Carry a material qualified event to the enrolled claim before recomputation; do not let the event label itself transition the regime. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
