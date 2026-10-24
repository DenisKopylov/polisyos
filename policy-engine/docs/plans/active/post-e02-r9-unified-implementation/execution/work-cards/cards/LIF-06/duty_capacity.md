# LIF-06.duty_capacity — Допускать только обслуживаемые duties

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-06](../../parents/LIF-06.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Selected duty uses measured capacity and LIF04 terms/age; review/miss is not service.

**Предпочтительное решение.** Bind existing LIF04 selector; LIF06 eligibility, OPS08 measurement, LIF02 conditional currentness.

**Граница владельца.** No duty/currentness writer transfer.

**Входы.** LIF04 duty/age/due, OPS08 headroom, physical allocations, LIF02 only if enrolled.

**Выход и consumer.** Eligibility/defer to LIF04, currentness to LIF02 if selected.

**Что можно готовить независимо.** Prepare the duty selector and measured resource/profile interfaces independently; actual measured admission and live allocation charge join only for a selected resource-bound duty.

**Где результат соединяется с другими.** Only an asserted resource-bound selected duty composes LIF-04 terms with LIF-06 measured admission and live-allocation evidence; otherwise ordinary duty selection remains independent.

**Positive.** Older eligible duty served or bounded; only dependent claim limited.

**Distinguishing negative.** Review/retry resets age or v1 silently downgraded.

**Matched removal.** Remove capacity/age join; reader fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: Consume committed duty/operation and live allocation; LIF04 remains owner.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-06.physical_admission](../../cards/LIF-06/physical_admission.md) | Only when the selected LIF-04 service duty asserts a resource-bound eligibility/measurement guarantee; ordinary duty policy does not require this admission result. |
| Composition output (не start gate) [LIF-06.allocation_lifetime](../../cards/LIF-06/allocation_lifetime.md) | Only for that selected resource-bound duty, using actual live allocation through release; queue status, TTL or transfer cannot substitute. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bounded overload preserves duty/currentness.
  `task.positive[1]`
- **execute** — Progress consumer status.
  `task.surface`
- **execute** — Service/fake-review/v1-v2 duty.
  `task.acceptance_steps[6]`; `task.acceptance_steps[7]`; `task.acceptance_steps[8]`
- **execute** — R17 duty capacity and removal.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — Queue policy at LIF04 selector.
  `solution.composition_contracts[6]`
- **execute** — Review unresolved/durable duty.
  `solution.composition_contracts[8]`; `solution.composition_contracts[9]`
- **execute** — Progress surface.
  `solution.acceptance_discriminators[4]`
- **execute** — Age/fake review/policy transition.
  `solution.acceptance_discriminators[9]`; `solution.acceptance_discriminators[10]`; `solution.acceptance_discriminators[11]`
- **execute** — task.r19_extension.question_slices[1] crosswalks by actual value to question_ids[1]. Pre-admits the selected claim duty against measured OPS-08 capacity/commitments while retaining nested denominator and scoped revalidation.
  `task.r19_extension.question_slices[1]` (`R18-D16-Q01`); `task.r19_extension.question_ids[1]` (`R18-D16-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
