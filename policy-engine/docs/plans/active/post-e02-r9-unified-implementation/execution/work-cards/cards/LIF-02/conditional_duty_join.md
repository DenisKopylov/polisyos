# LIF-02.conditional_duty_join — Условно применить missed-duty status

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-02](../../parents/LIF-02.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Missed committed interval limits only enrolled claims dependent on selected duty.

**Предпочтительное решение.** Use the same native Claim Ledger currentness owner to consume LIF04 duty outcomes and, only when selected, OPS11 standing-duty witness plus LIF06 eligibility/OPS08 measured profile; no scheduler, currentness writer, or synthetic event.

**Граница владельца.** Same LIF02 lease; LIF04 owns duty, LIF06 capacity.

**Входы.** Native enrolled claim–duty relation and required coverage contract; if absent/unknown, this promised coverage is limited rather than the join bypassed.; LIF-04 task.deliverable: actual stable duty/admission commitment and due/continuation/cutoff/lapse outcome, only when the relation and coverage contract establish a continuing custody service promise.; OPS-11 task.deliverable/task.positive[0]: selected standing-duty activation, accepted transfer, or authorized cutoff bound to the same enrolled claim and coverage interval, only when commissioned standing-custody activation/transfer/cutoff is asserted.; LIF-06 task.deliverable: selected resource-policy eligibility, and OPS-08 task.deliverable/task.positive[0]: actual selected profile plus measured envelope/window/limitations, only when the service claim asserts that qualified resource eligibility and measured bound.; Fresh selected UI-02/UI-19/API history/currentness reader; due-without-event remains observable without an emitted event or heartbeat.

**Выход и consumer.** Scoped overdue projection to selected fresh reader.

**Что можно готовить независимо.** Prepare against the agreed scoped interfaces only; LIF04/OPS11/LIF06/OPS08 can prepare independently. No whole-task wait, synthetic event, or new start prerequisite; actual selected witnesses join at composition.

**Где результат соединяется с другими.** Fresh selected history/currentness readers apply due/continuation only to the enrolled dependent coverage; a missed interval remains observable without an event or heartbeat.

**Positive.** Missed due without event/heartbeat limits affected; independent claim remains usable.

**Distinguishing negative.** Retry/review/unrelated duty is not service or global downgrade.

**Matched removal.** Remove due/currentness join but retain markers; affected-only test fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Source: `task.acceptance_dependencies[1]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-04](../../parents/LIF-04.md) | `conditional_acceptance_requirements:composition`: Actual stable duty/admission commitment and due/continuation/cutoff/lapse outcome, with selected native duty and resource evidence for the property claimed<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The native enrolled claim–duty relation and coverage contract establish a continuing custody service promise; unknown/missing required relation limits that coverage rather than bypassing the join |
| Supplier [OPS-11](../../parents/OPS-11.md) | `conditional_acceptance_requirements:composition`: Actual selected standing-duty activation/accepted transfer or authorized cutoff bound to the enrolled claim and coverage interval<br>Source: `task.conditional_acceptance_requirements[1]`.<br>Условия: The selected coverage contract asserts commissioned standing-custody activation/transfer/cutoff supplied through OPS-11 |
| Supplier [LIF-06](../../parents/LIF-06.md) | `conditional_acceptance_requirements:composition`: Actual selected resource-policy eligibility and measured envelope/window/limitations, bound to the same admitted duty and service guarantee<br>Source: `task.conditional_acceptance_requirements[2]`.<br>Условия: The selected service claim asserts the LIF-06/OPS-08 qualified resource eligibility and measured service bound |
| Supplier [OPS-08](../../parents/OPS-08.md) | `conditional_acceptance_requirements:composition`: Actual selected resource-policy eligibility and measured envelope/window/limitations, bound to the same admitted duty and service guarantee<br>Source: `task.conditional_acceptance_requirements[2]`.<br>Условия: The selected service claim asserts the LIF-06/OPS-08 qualified resource eligibility and measured service bound |
| Composition output (не start gate) [LIF-02.native_event_replay](../../cards/LIF-02/native_event_replay.md) | Only when the enrolled claim also selects the native event currentness basis; due-without-event duty status remains observable and does not wait for an event. |
| Composition output (не start gate) [LIF-02.bounded_observation_order](../../cards/LIF-02/bounded_observation_order.md) | Only when the enrolled claim also selects the bounded observation/as-of basis; duty status does not require an observation or synthetic event. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Missed selected duty changes dependent claim only.
  `task.acceptance_steps[6]`
- **execute** — Selected duty composition.
  `solution.composition_contracts[4]`
- **execute** — Missed committed due with no event.
  `solution.acceptance_discriminators[5]`
- **execute** — task.r19_extension.question_slices[13] crosswalks by actual value to question_ids[9]. Joins selected missed/unknown duty to only enrolled dependent claims, including a due missed during outage with no event.
  `task.r19_extension.question_slices[13]` (`R18-D16-Q01`); `task.r19_extension.question_ids[9]` (`R18-D16-Q01`)
- **execute** — task.r19_extension.question_slices[14] crosswalks by actual value to question_ids[10]. Limits only enrolled claims dependent on missed/unevaluable duty; unrelated claims and candidates remain usable.
  `task.r19_extension.question_slices[14]` (`R18-D16-Q02`); `task.r19_extension.question_ids[10]` (`R18-D16-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
