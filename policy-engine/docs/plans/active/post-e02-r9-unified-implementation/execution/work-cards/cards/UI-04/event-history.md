# UI-04.event-history — Записывать attributed DS13 events

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [UI-04](../../parents/UI-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Response/correction/revocation/supersession/law-7 events append-only и связаны с immutable parent ArtifactRef/profile, actor/authority/kind/time; formal act, informal evidence и PolicyOS reaction различны.

**Предпочтительное решение.** На P0 rebinding найти actual DS13 producer; переиспользовать existing runtime owner или, если отсутствует, UI-04 назначает один typed producer в той же runtime boundary. AccessAuditTrail только authorized reads.

**Граница владельца.** UI-04 owns confirmed event producer/output only; external institutions own decisions; no moderation/court/notification/second audit ledger.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** UI-03 identity; actual attributed response/acts; consent/rights and LIF-02/LIF-05 interfaces.

**Выход и consumer.** Persisted event с parent/version, actor/authority, event kind, time roles, consent/rights и formal/informal/reaction status.

**Что можно готовить независимо.** Сначала bind event owner и contract; consumer prep после agreed interface.

**Где результат соединяется с другими.** Feed читает event output; event не устанавливает causal effect или institutional act сверх typed evidence.

**Positive.** Атрибутированный ответ дополняет историю без изменения parent bytes.

**Distinguishing negative.** Self-assertion, collapsed status, auto-resolution, missing consent или overwritten parent refused.

**Matched removal.** Удалить persisted event/parent binding с markers: fresh reader не восстанавливает lineage.

**Граница контекста.** Не считать access audit комментарной историей; producer символ и точный lease подтвердить на P0.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Conditional only where selected persisted event/history placements retain, disclose, delete or restore governed content/identifiers: event persistence and fresh managed readers consume the actual owner-qualified placement generation and permitted receipt/existence decision before the protected effect at composition. Reader preparation remains independent.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The selected history/publication path retains, discloses, deletes or restores rights-governed content or identifying metadata |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Binds actual append-only event producer and exact parent/actor/authority/kind/time/consent contract; access audit is not the event store. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`
- **binding** — This source field contributes to event-history's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[1].
  `solution.acceptance_discriminators[1]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.input_resolution_rule, solution.inputs_to_resolve[0], solution.inputs_to_resolve[1].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`
- **binding** — tasks.json#UI-04.task.r19_extension.question_slices[1] value-matches question_ids[1]. Current destination is right but current coverage's reason incorrectly characterizes this slice as a LIF-02 consumer; the exact slice is the primary-writer event contract. Keep it bound to event-history's already-executed producer steps 0..2: append to the exact edition with dissent/time/authority, without auto-resolution.
  `task.r19_extension.question_slices[1]` (`R18-D12-Q05`); `task.r19_extension.question_ids[1]` (`R18-D12-Q05`)
- **binding** — tasks.json#UI-04.task.r19_extension.question_slices[3] value-matches question_ids[4] (not question_ids[3]). Event-history is the exact-parent append owner; its preferred-solution implementation_steps[0..2] already execute the producer, so this question route binds the S13 event's formal/informal/PolicyOS distinctions rather than appointing a second writer.
  `task.r19_extension.question_slices[3]` (`R18-D22-Q03`); `task.r19_extension.question_ids[4]` (`R18-D22-Q03`)
- **binding** — tasks.json#UI-04.task.r19_extension.question_slices[4] value-matches question_ids[5] (not question_ids[4]). Event-history is the accountable typed-event owner, and its existing execute steps produce linked report/reply/formal-outcome/reaction events; bind the slice's consent/audience and no-ruling semantics there. Do not turn optional investigation/adjudication into a blocking all-of input.
  `task.r19_extension.question_slices[4]` (`R18-D22-Q05`); `task.r19_extension.question_ids[5]` (`R18-D22-Q05`)
- **binding** — tasks.json#UI-04.task.r19_extension.question_slices[5] value-matches question_ids[3] (not question_ids[5]). Event-history's existing producer steps own append-only attribution/supersession; the question route binds the no-adjudication/no-overwrite constraint, not external supervisory work.
  `task.r19_extension.question_slices[5]` (`R18-D14-Q05`); `task.r19_extension.question_ids[3]` (`R18-D14-Q05`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — Feed input must retain the exact immutable parent/version relation so the fresh history view can resolve the selected rendition lineage. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Event parent/actor/count and other attached metadata remain part of the rights-qualified persisted event, not a label-only redaction. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
