# LIF-02.native_event_replay — Сохранить event replay и publication fence

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-02](../../parents/LIF-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** At C/W replay (C,W], refuse passed floor, couple dedupe/effect, append invalidation and fence on source/right cut.

**Предпочтительное решение.** Extend source-event + Claim/Decision Validity owner; source supplies event/cut; CAP04 only actual event receipt.

**Граница владельца.** All cards same `write:claim-currentness` + `resource:source/{source_profile}/generation`; E02 paths unresolved, no disjointness.

**Входы.** Source journal/cut/floor; CAP04 event; LIF01 use; publisher head; rights generation.

**Выход и consumer.** Persisted enrollment/replay/currentness to fresh reader.

**Что можно готовить независимо.** Single currentness owner for all cards.

**Где результат соединяется с другими.** Fresh currentness readers use this source-native replay/fence path only when a qualified event route is selected; bounded observation remains an alternative.

**Positive.** Pre/post enrollment and unrelated source control.

**Distinguishing negative.** Event before enrollment, expired floor, dedupe crash or publication race.

**Matched removal.** Remove replay/fence but retain markers; behavioral gate fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume exact claim/use for enrollment; LIF01 remains owner.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-04](../../parents/CAP-04.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[1]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-02.bounded_observation_order](../../cards/LIF-02/bounded_observation_order.md) | Only as the selected no-feed CAP-04 observation/as-of alternative bound to the CAP-02 root/profile/coverage and local ordered head; it is not a simultaneous input or proof of native event continuity. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Native replay/fence, surface, rollback and migration.
  `task.deliverable`; `task.positive[0]`; `task.positive[1]`; `task.adversarial[0]`; `task.removal[0]`; `task.removal[1]`; `task.surface`; `task.rollback`; `task.migration`
- **execute** — CAP04 event and R15 currentness tests.
  `task.acceptance_evidence_requirements[0]`; `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — R16 currentness/removal.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`
- **execute** — R17 sole currentness owner/tests.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — Native C/W/replay/effect/fence.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Generic source/replay/migration/owner semantics.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **execute** — Replay and removal discriminators.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Cutoff/re-evaluation and source/right/publisher inputs; no supplier appointment.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`
- **execute** — task.r19_extension.question_slices[0] crosswalks by actual value to question_ids[8]. Owns enrollment, source cursor/replay, currentness and as-of cutoff; LIF-03 separately consumes the same continuity identity at frontier commit.
  `task.r19_extension.question_slices[0]` (`R18-D15-Q02`); `task.r19_extension.question_ids[8]` (`R18-D15-Q02`)
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[1]. Enrolled native event replay must invalidate only exact dependent uses and enforce the replay floor.
  `task.r19_extension.question_slices[2]` (`R18-D04-Q03`); `task.r19_extension.question_ids[1]` (`R18-D04-Q03`)
- **execute** — task.r19_extension.question_slices[3] crosswalks by actual value to question_ids[2]. Source-cut replay and claim-head fencing implement immediate, scoped event invalidation.
  `task.r19_extension.question_slices[3]` (`R18-D04-Q06`); `task.r19_extension.question_ids[2]` (`R18-D04-Q06`)
- **execute** — task.r19_extension.question_slices[4] crosswalks by actual value to question_ids[3]. Changed source/right must limit current use before rerun while retaining the old-as-known record.
  `task.r19_extension.question_slices[4]` (`R18-D07-Q02`); `task.r19_extension.question_ids[3]` (`R18-D07-Q02`)
- **execute** — task.r19_extension.question_slices[5] crosswalks by actual value to question_ids[4]. Consumes enrolled cuts and upstream currentness without taking over source qualification.
  `task.r19_extension.question_slices[5]` (`R18-D10-Q01`); `task.r19_extension.question_ids[4]` (`R18-D10-Q01`)
- **execute** — task.r19_extension.question_slices[6] crosswalks by actual value to question_ids[5]. A source/time-cut quality regression needs scoped currentness reaction; a silent feed is not no-change, while context-only variation does not requalify a call.
  `task.r19_extension.question_slices[6]` (`R18-D11-Q01`); `task.r19_extension.question_ids[5]` (`R18-D11-Q01`)
- **execute** — task.r19_extension.question_slices[7] crosswalks by actual value to question_ids[6]. A material enrolled source/content change immediately fences affected current uses even when recomputation waits.
  `task.r19_extension.question_slices[7]` (`R18-D12-Q05`); `task.r19_extension.question_ids[6]` (`R18-D12-Q05`)
- **execute** — task.r19_extension.question_slices[8] crosswalks by actual value to question_ids[13]. An enrolled event/correction must limit its dependent claim before heavy reevaluation.
  `task.r19_extension.question_slices[8]` (`R18-D22-Q01`); `task.r19_extension.question_ids[13]` (`R18-D22-Q01`)
- **execute** — task.r19_extension.question_slices[10] crosswalks by actual value to question_ids[15]. Reacts only where the premise is enrolled; an answerer-only change may alter attribution without global staleness.
  `task.r19_extension.question_slices[10]` (`R18-D22-Q04`); `task.r19_extension.question_ids[15]` (`R18-D22-Q04`)
- **execute** — task.r19_extension.question_slices[11] crosswalks by actual value to question_ids[16]. Fences the exact enrolled predicate before causal rerun, preserving unrelated claims.
  `task.r19_extension.question_slices[11]` (`R18-D22-Q05`); `task.r19_extension.question_ids[16]` (`R18-D22-Q05`)
- **execute** — task.r19_extension.question_slices[12] crosswalks by actual value to question_ids[7]. Applies an accepted event to enrolled claims at bounded replay and changes currentness only.
  `task.r19_extension.question_slices[12]` (`R18-D14-Q02`); `task.r19_extension.question_ids[7]` (`R18-D14-Q02`)
- **execute** — task.r19_extension.question_slices[15] crosswalks by actual value to question_ids[11]. Replays accepted support events against enrolled dependencies and fresh currentness reads.
  `task.r19_extension.question_slices[15]` (`R18-D17-Q04`); `task.r19_extension.question_ids[11]` (`R18-D17-Q04`)
- **execute** — task.r19_extension.question_slices[16] crosswalks by actual value to question_ids[12]. Carries the native fence through affected recomposition to the API/MACHINE current-state reader.
  `task.r19_extension.question_slices[16]` (`R18-D20-Q05`); `task.r19_extension.question_ids[12]` (`R18-D20-Q05`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[1]` — R25 LIF-02 route: genuine CAP-04 source events are replayed here; keep this event-only subclause separate from the no-webhook/observation path, with no watcher or synthetic event. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[9]` — R25 LIF-02 route: genuine CAP-04 source events are replayed here; keep this event-only subclause separate from the no-webhook/observation path, with no watcher or synthetic event. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
