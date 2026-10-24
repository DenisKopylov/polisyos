# LIF-04.durable_service_commitment — Сохранить committed service duty

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-04](../../parents/LIF-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Duty retains identity, version/terms, age and due trigger across restart/review/policy change.

**Предпочтительное решение.** Extend same ControlPlaneStore; consume LIF06 capacity and OPS successor; no scheduler.

**Граница владельца.** Same LIF04 lease; LIF04 duty, LIF06 capacity, LIF02 conditional currentness.

**Входы.** Committed duty; LIF06 eligibility; OPS transition; LIF02 only when claim enrolled.

**Выход и consumer.** Persisted due/continuation/overdue to job reader and conditional LIF02.

**Что можно готовить независимо.** R25 service slice retained.

**Где результат соединяется с другими.** Fresh due/continuation readers consume the durable duty; LIF-02 joins only for an enrolled coverage promise, OPS-11 only for asserted standing-duty activation/transfer/cutoff, and LIF-06 plus the OPS-08 selected profile only for asserted resource-bound guarantees. Effect recovery joins only for the selected protected service action.

**Positive.** Older work gets bounded service opportunity; v1 survives due/restart.

**Distinguishing negative.** Review/retry resets age or silently downgrades old duty.

**Matched removal.** Remove real service/due continuation, keep markers; fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Selected enrolled duty claim only; no blanket gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-04.effect_recovery](../../cards/LIF-04/effect_recovery.md) | Only when the selected due-service transition dispatches this protected provider action; review, continuation, cutoff and overdue outcomes need no effect receipt. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Service opportunity and fake review.
  `task.acceptance_steps[5]`; `task.acceptance_steps[6]`
- **execute** — Versioned duty missed-due restart.
  `task.acceptance_steps[8]`
- **execute** — R17 duty restart/review.
  `task.r17_extension.requirement`; `task.r17_extension.positive`
- **execute** — LIF06 capacity and unresolved review.
  `solution.composition_contracts[4]`; `solution.composition_contracts[5]`
- **execute** — Persistent duty age/trigger.
  `solution.composition_contracts[7]`
- **execute** — Actual service and bounded outcome.
  `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`
- **execute** — Old v1 vs new v2.
  `solution.acceptance_discriminators[7]`
- **binding** — OPS successor/cutoff.
  `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
