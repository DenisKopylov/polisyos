# LIF-06.allocation_lifetime — Сохранять charge живых allocation

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [LIF-06](../../parents/LIF-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Allocation charged until actual release; nested/shared/IPC/copies cannot invent capacity.

**Предпочтительное решение.** Extend native allocation owner and OPS08 reconciliation, not job status/TTL.

**Граница владельца.** Same LIF06 lease; no universal allocator ledger.

**Входы.** Operation/allocation, shared/private use, release/transfer and actual headroom.

**Выход и consumer.** Live allocation charge read by admission/recovery.

**Что можно готовить независимо.** No per-object tracing.

**Где результат соединяется с другими.** Admission/recovery readers consume the actual still-live charge through release; terminal state, expiry or transfer does not clear it.

**Positive.** 60/100 parent cannot admit 50/100 child; shared cache once until release.

**Distinguishing negative.** Yield/expiry/duplicate transfer erases live usage.

**Matched removal.** Remove lifetime reconciliation with markers intact; nested probe fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: Consume committed duty/operation and live allocation; LIF04 remains owner.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Aggregate reservation/release.
  `task.removal[1]`
- **execute** — Nested/live allocation.
  `task.acceptance_steps[4]`; `task.acceptance_steps[5]`
- **execute** — Nested live allocation.
  `solution.implementation_steps[4]`
- **execute** — Identity and transfer.
  `solution.composition_contracts[5]`
- **execute** — Conservative lifetime.
  `solution.composition_contracts[7]`
- **execute** — Nested/shared allocation.
  `solution.acceptance_discriminators[7]`; `solution.acceptance_discriminators[8]`
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[2]. Keeps allocation charged through live process/effect and nested work until actual release/reconciliation.
  `task.r19_extension.question_slices[2]` (`R18-D16-Q02`); `task.r19_extension.question_ids[2]` (`R18-D16-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
