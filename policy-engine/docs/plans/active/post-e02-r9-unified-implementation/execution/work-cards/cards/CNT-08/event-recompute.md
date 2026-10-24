# CNT-08.event-recompute — Переоценивать только affected uses по verified event

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [CNT-08](../../parents/CNT-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Verified correction/revocation/legal/source/permission event recomputes status for exactly dependent uses, updates same-generation projections, and leaves unrelated claims current; prior basis remains immutable.

**Предпочтительное решение.** Reuse LIF-07 only for influence/descendant closure and existing change consumers. Compose a qualified event with the selected basis manifest, then let LIF-02 own the currentness decision/head and selected Scientist claim-support readers consume it. CNT-08 does not write a second cascade or currentness result.

**Граница владельца.** LIF-07 owns influence parents and influence/descendant closure under its native canonical lease; LIF-02 owns currentness decision and claim head under its native canonical lease. Custodians/issuer supply events; Scientist and selected UI/CNT/DES readers consume owner results. CNT-08 is a composition reader/bridge, not a second cascade or status writer. Exact paths and semantic overlaps unresolved after E02; do not presume disjoint.

**Входы.** Basis-branches manifest; verified source/issuer/rights-holder/community change event; LIF-07 influence/descendant closure; and LIF-02 currentness/head interface for the selected affected uses. CNT-04/CAP-05/CNT-07 remain conditional event sources.

**Выход и consumer.** Fresh-consumer evidence that the qualified event was compared against the selected immutable basis and LIF-07 affected-use closure, and that the LIF-02 owner currentness/head result changed only affected uses; CNT-08 emits no second status/head.

**Что можно готовить независимо.** Manifest, consumer contract and read-only affected-use probe can be prepared independently. Actual composition waits for a real verified selected event and agreed LIF-07/LIF-02 interfaces, accepted E02 binding, exact leases and permit; no sibling preparation barrier or global invalidation.

**Где результат соединяется с другими.** LIF-07 supplies influence/descendant closure only; LIF-02 owns currentness decision/head. Fresh Scientist claim-support/currentness readers consume the LIF-02 result, and selected surfaces apply their own audience filter.

**Positive.** Проверенная correction меняет только связанные ветви/claims и их currentness; prior basis остаётся immutable, несвязанные claims остаются current, а решение/head пишет только LIF-02.

**Distinguishing negative.** Порядок прихода не выбирает применимое право; одинаковые bytes не стирают измеренный drift; производный текст не stale-ит все claims; общий cache не становится подтверждением.

**Matched removal.** Оставь то же verified event, immutable basis и LIF-07 closure, но отключи event→basis edge/scoped cascade. Неизменённая семантическая проверка ожидает обновление ровно affected uses и currentness unrelated uses; false-green либо лишняя stale-метка означает, что эта проверка должна FAIL при отключённом механизме. Отдельное отсутствие события не запускает synthetic recompute и не является removal probe.

**Граница контекста.** Second sequence checkpoint is final composition only: actual event is conditional/external, LIF-07 owns influence closure, and LIF-02 owns currentness/head. CNT-08 creates neither a cascade nor a second currentness writer.

## Первые действия и передача

1. После принятого E02 и source/lease rebind сверь event interface с владельцами LIF-07 influence/descendant closure и LIF-02 currentness decision/head; зафиксируй точного поставщика выбранного correction/revocation/change event.
2. Сопоставь проверенное событие с immutable basis и LIF-07 closure, чтобы получить только затронутые uses. Право/закон/permission подтверждает свой custodian; CNT-08 не выводит событие из даты, текста, hash или очередности поступления.
3. Передай scoped affected-use set владельцу LIF-02 для решения/head и прочитай его результат свежим Scientist claim-support/currentness reader и выбранными audience-filtered surfaces.
4. При отсутствии upstream event не синтезируй событие; независимые LIF-02 expiry/missed-duty rules продолжают действовать. Отсутствующий LIF-07/LIF-02 bridge — внутренняя интеграционная работа, не внешний blocker.

**Ответственность и handoff.** Поставщик/issuer/rights holder/community authority отвечает за событие; LIF-07 владеет influence parents и affected-use closure; LIF-02 владеет currentness decision и claim head. CNT-08 только связывает результаты. Handoff: свежий Scientist claim-support/currentness reader и выбранные surface consumers; ни второй cascade, ни второй status writer.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-06](../../parents/CNT-06.md) | `direct:owner_readiness`: ClaimRecord target/estimand/method and conditional calibration relation to compare or recompute applicable claims.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-07](../../parents/LIF-07.md) | `direct:owner_readiness`: Native influence parents, event impact set and cascade/currentness result; don't recreate owner.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `interface_reference:reference_only_no_new_gate`: Consume the native currentness decision/head at composition after LIF-07 supplies influence/descendant closure. This is an agreed-interface consumption map only; it adds no canonical task edge or start gate and CNT-08 remains a reader.<br>Source parent `LIF-02`: `task.deliverable`.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |
| Composition output (не start gate) [CNT-08.basis-branches](../../cards/CNT-08/basis-branches.md) | Only for the selected same-scope composition described by this card: LIF-07 supplies influence/descendant closure only; LIF-02 owns currentness decision/head. Fresh Scientist claim-support/currentness readers consume the LIF-02 result, and selected surfaces apply their own audience filter. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `task.external_inputs`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `task.removal`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `task.surface[1]`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `task.surface[3]`; `task.rollback`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `solution.implementation_steps[2]`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `solution.composition_contracts[2]`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `solution.acceptance_discriminators[2]`
- **execute** — These clauses bind authentic correction/revocation/change inputs to scoped impact analysis, affected-use refresh and projection; event suppliers stay external and LIF-07 owns cascade.
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — After a qualified legal/participation premise change, refresh only linked claims; basis comparison itself does not create the event. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Apply qualified child-specific change only to affected dependent uses; do not re-decide the legal/permission source. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[8]` — Propagate measured support drift only through affected claim dependencies/currentness. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[9]` — A qualified correction changes only dependent branches/claims; retain historical basis. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[10]` — Refresh affected legal-basis uses after qualified correction, without counting summaries as independent authority. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[11]` — Refresh only claims dependent on a changed bridge/source version. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
