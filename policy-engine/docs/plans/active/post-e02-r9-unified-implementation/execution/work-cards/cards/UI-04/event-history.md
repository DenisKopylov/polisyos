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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Conditional only where selected persisted event/history placements retain, disclose, delete or restore governed content/identifiers: event persistence and fresh managed readers consume the actual owner-qualified placement generation and permitted receipt/existence decision before the protected effect at composition. Reader preparation remains independent.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: The selected history/publication path retains, discloses, deletes or restores rights-governed content or identifying metadata |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Q05 consumes actual LIF-02 scoped reaction/as-of; historical signature cannot render current. Source selectors: task.r19_extension.question_ids[1], task.r19_extension.question_slices[1].
  `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[1]`
- **binding** — Q03 appends correction/reply to exact parent and separates informal evidence, formal act and PolicyOS reaction. Source selectors: task.r19_extension.question_ids[4], task.r19_extension.question_slices[3].
  `task.r19_extension.question_slices[3]`; `task.r19_extension.question_ids[4]`
- **binding** — Q05 links report/reply/formal outcome/own reaction with distinct authority/time/consent. Source selectors: task.r19_extension.question_ids[5], task.r19_extension.question_slices[4].
  `task.r19_extension.question_slices[4]`; `task.r19_extension.question_ids[5]`
- **binding** — Q05 appends attributed response/supersession without adjudicating or overwriting the original. Source selectors: task.r19_extension.question_ids[3], task.r19_extension.question_slices[5].
  `task.r19_extension.question_slices[5]`; `task.r19_extension.question_ids[3]`
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

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
