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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume exact claim/use for enrollment; LIF01 remains owner.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-04](../../parents/CAP-04.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-02.bounded_observation_order](../../cards/LIF-02/bounded_observation_order.md) | Only as the selected no-feed CAP-04 observation/as-of alternative bound to the CAP-02 root/profile/coverage and local ordered head; it is not a simultaneous input or proof of native event continuity. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Native replay/fence, surface, rollback and migration.
  `task.deliverable`; `task.positive[0]`; `task.positive[1]`; `task.adversarial[0]`; `task.removal[0]`; `task.removal[1]`; `task.surface`; `task.rollback`; `task.migration`
- **execute** — CAP04 event and R15 currentness tests.
  `task.acceptance_evidence_requirements[0]`; `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — R16 currentness/removal.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`
- **execute** — R17 sole currentness owner/tests.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — R18-D03-Q03 native replay/cut.
  `task.r19_extension.question_slices[0]`
- **execute** — R18 exact enrolled source/time changes; derivative/answerer change not global.
  `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[5]`; `task.r19_extension.question_slices[6]`; `task.r19_extension.question_slices[7]`; `task.r19_extension.question_slices[8]`; `task.r19_extension.question_slices[9]`; `task.r19_extension.question_slices[10]`; `task.r19_extension.question_slices[11]`; `task.r19_extension.question_slices[12]`; `task.r19_extension.question_slices[13]`; `task.r19_extension.question_slices[14]`; `task.r19_extension.question_slices[15]`; `task.r19_extension.question_slices[16]`
- **binding** — ID mirrors U064.
  `task.r19_extension.question_ids[0]`
- **binding** — IDs mirror U066-U076 native changes.
  `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[6]`; `task.r19_extension.question_ids[7]`; `task.r19_extension.question_ids[8]`; `task.r19_extension.question_ids[9]`; `task.r19_extension.question_ids[10]`; `task.r19_extension.question_ids[11]`; `task.r19_extension.question_ids[12]`
- **binding** — IDs mirror U079-U080 support events.
  `task.r19_extension.question_ids[15]`; `task.r19_extension.question_ids[16]`
- **execute** — Native C/W/replay/effect/fence.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Generic source/replay/migration/owner semantics.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **execute** — Replay and removal discriminators.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Cutoff/re-evaluation and source/right/publisher inputs; no supplier appointment.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
