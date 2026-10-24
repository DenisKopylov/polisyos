# OPS-08.service-profile — Передавать измеренные пределы в durable duty

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [OPS-08](../../parents/OPS-08.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each custody/currentness duty’s selected service class is bounded by measured headroom/age targets and a truthful terminal/review/limited outcome; actual duty age and due trigger remain durable across policy change/restart.

**Предпочтительное решение.** OPS-08 supplies only measured envelope and selected bounded progress-profile inputs to LIF-04’s existing due-intent selector. LIF-04 remains the duty/scheduler owner, LIF-06 the eligibility/admission owner, and LIF-02 the enrolled claim reaction/consumer. No new scheduler, approval gate or universal SLA.

**Граница владельца.** This is measured profile/input work under OPS-08 `resource:host/{host}/memory-disk`; it neither writes LIF-04 duty state nor LIF-02 claim currentness. Exact workload/profile paths and overlapping leases are resolved after accepted-source rebind.

**Входы.** OPS-08 `class-envelope` and `aggregate-cap` results; LIF-06 current eligibility and enforceable admission; LIF-04 persisted duty identity, policy version, original age and next trigger; LIF-02 actual selected claim-coverage consumer

**Выход и consumer.** Selected measured queue/progress envelope and bounded allowed outcomes consumed by LIF-04; composed duty outcome and overdue/limited claim state remain LIF-04/LIF-02 outputs.

**Что можно готовить независимо.** Measure profile candidates within an existing safe envelope. The progress guarantee cannot be declared until LIF-04’s durable commitment and fresh LIF-02 consumer are composed under the selected support/clock basis.

**Где результат соединяется с другими.** For sustained eligible load, LIF-04 either makes the promised service opportunity or records its selected bounded terminal/review disposition without resetting age; a missed custody/revocation duty reaches only its enrolled claim through LIF-02. Current safety, rights and caps apply immediately.

**Positive.** A review callback, new retry ID, TTL expiry, policy v2 or lost/duplicate wakeup cannot silently count as service, erase old admitted terms, or conceal overdue coverage.

**Distinguishing negative.** Remove committed-policy persistence or durable trigger/overdue-to-claim reaction while retaining queue-age/review markers; the old duty and affected-claim probe fails.

**Matched removal.** This card authors only the measured/profile input; it does not appoint a service owner or implement a scheduler. R24-03/04 semantics remain LIF-04/LIF-02. G07 is its navigation home because the result qualifies ongoing custody coverage.

**Граница контекста.** G07 is a navigation home for the ongoing custody-duty input. This card emits only measured profile/coverage inputs; it does not appoint the duty owner, persist LIF-04 service terms, create a scheduler, or set LIF-02 claim status. Independent measurement and contract preparation remain possible; the selected duty composition joins actual aggregate admission and class-envelope outputs.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: All writers/consumers use the accepted source and task-scoped rebind; preserve parent dispatch, not a new all-task edge.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Consume the actual runtime process/worker classes, not agent/reviewer concurrency or a guessed process census.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Use the single native aggregate admission/eligibility owner and actual usage receipt; no second shared ledger.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `interface_reference:reference_only_no_new_gate`: Cross-card contract only: LIF-04 remains the durable service/due-intent owner; OPS-08 supplies measured input and is joined at completion, not a new start/scheduler edge.<br>Source parent `LIF-04`: `task.deliverable`.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |
| Supplier [LIF-02](../../parents/LIF-02.md) | `interface_reference:reference_only_no_new_gate`: Cross-card final consumer: selected missed duty changes only its enrolled claim/coverage through LIF-02; no OPS-08 claim writer.<br>Source parent `LIF-02`: `task.deliverable`.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |
| Composition output (не start gate) [OPS-08.aggregate-cap](../../cards/OPS-08/aggregate-cap.md) | Only for the selected same-scope composition described by this card: For sustained eligible load, LIF-04 either makes the promised service opportunity or records its selected bounded terminal/review disposition without resetting age; a missed custody/revocation duty reaches only its enrolled claim through LIF-02. Current safety, rights and caps apply immediately. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [OPS-08.class-envelope](../../cards/OPS-08/class-envelope.md) | Only for the selected same-scope composition described by this card: For sustained eligible load, LIF-04 either makes the promised service opportunity or records its selected bounded terminal/review disposition without resetting age; a missed custody/revocation duty reaches only its enrolled claim through LIF-02. Current safety, rights and caps apply immediately. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for service-profile; selectors task.r19_extension.question_ids[3], solution.composition_contracts[3], solution.composition_contracts[5], solution.composition_contracts[6] remain load-bearing.
  `solution.composition_contracts[3]`; `solution.composition_contracts[5]`; `solution.composition_contracts[6]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for service-profile; selectors task.acceptance_steps[6], task.acceptance_steps[7], task.acceptance_steps[8], task.r19_extension.question_slices[3], solution.acceptance_discriminators[5], solution.acceptance_discriminators[6], solution.acceptance_discriminators[7] are checked at its actual reader/sink. Bundled subclauses: U052:{"question_id":"R18-D16-Q01","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q01","mechanism_ids":["S16-M1"],"role":"consumer"}.
  `task.acceptance_steps[6]`; `task.acceptance_steps[7]`; `task.acceptance_steps[8]`; `solution.acceptance_discriminators[5]`; `solution.acceptance_discriminators[6]`; `solution.acceptance_discriminators[7]`
- **join** — OPS-08 supplies the measured bounded service-class input for custody/currentness duties; LIF-04 persists due terms and LIF-02 consumes missed-duty effects.
  `task.r19_extension.question_slices[3]` (`R18-D16-Q01`); `task.r19_extension.question_ids[3]` (`R18-D16-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
