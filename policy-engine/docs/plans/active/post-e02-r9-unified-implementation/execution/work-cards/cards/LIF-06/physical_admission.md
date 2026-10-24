# LIF-06.physical_admission — Измерить physical admission

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [LIF-06](../../parents/LIF-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only measured dimensions with actual enforcement hard-admit; custody/control reserve remains protected.

**Предпочтительное решение.** One LIF06 admission owner; OPS08 supplies host/process/storage enforcement.

**Граница владельца.** `write:resource-admission`,`resource:host/{host}/memory-disk`; E02 seam unresolved.

**Входы.** OPS08 profile/headroom, resource vector, account/quota and terminal fan-in. Inputs do not appoint supplier.

**Выход и consumer.** Persisted bounded admit/defer/refuse to existing progress reader.

**Что можно готовить независимо.** Only measured dimensions hard-bound.

**Где результат соединяется с другими.** Existing progress/admission reader consumes a measured decision with terminal reserve and the current live-allocation charge; this is not a duty/service guarantee.

**Positive.** Work fits measured cap plus terminal reserve.

**Distinguishing negative.** Aggregate, live process, ENOSPC/429 or bulk saturation exceeds cap.

**Matched removal.** Remove real enforcement but retain fields; measurement fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-06.allocation_lifetime](../../cards/LIF-06/allocation_lifetime.md) | At the measured admission/recovery decision when shared or private live allocations affect available headroom; preparation can proceed independently. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Measured work plus reserve.
  `task.positive[0]`
- **execute** — Reserve removal.
  `task.removal[0]`
- **execute** — Physical cap removal.
  `task.removal[2]`
- **execute** — Native seam/vector/reserve.
  `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **execute** — Real controls, profiles and bounded dimensions.
  `solution.implementation_steps[6]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **binding** — Measured state/reserve/provider principal.
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **binding** — Measurement not production duty.
  `solution.composition_contracts[4]`
- **execute** — Measured profile/extensibility.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`
- **execute** — Bulk/control and new dimension.
  `solution.acceptance_discriminators[5]`; `solution.acceptance_discriminators[6]`
- **binding** — Process scope/provider quota/host and OPS inputs; not supplier appointment.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`
- **binding** — Missing native owner assigned LIF06, not OPS scheduler.
  `solution.inputs_to_resolve[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
