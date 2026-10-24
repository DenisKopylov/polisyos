# LIF-06.material_support_accounting — Связать material support с exact scope

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [LIF-06](../../parents/LIF-06.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Cost/check/energy/copies complete only for exact edition/duty and reconciled denominator.

**Предпочтительное решение.** Consume OPS08/storage/metric receipts; no invented universal meter.

**Граница владельца.** LIF06 admission, OPS08 physical, storage copies, metric edition remain owners.

**Входы.** Edition/duty, check cost, placement/coverage, energy and rights.

**Выход и consumer.** Per-edition support receipt with denominator/partial state.

**Что можно готовить независимо.** Refines R25 material consumer.

**Где результат соединяется с другими.** Missing meter limits only claim requiring it.

**Positive.** Replicas once; aggregate/child not double-counted.

**Distinguishing negative.** Hash hides copies, omission reported complete.

**Matched removal.** Remove receipt but keep label; partial/unknown.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — R18-D19-Q02 check cost + paired ID.
  `task.r19_extension.question_slices[3]`; `task.r19_extension.question_ids[3]`
- **execute** — R18-D19-Q04 copies + paired ID.
  `task.r19_extension.question_slices[4]`; `task.r19_extension.question_ids[4]`
- **execute** — R18-D19-Q05 energy + paired ID.
  `task.r19_extension.question_slices[5]`; `task.r19_extension.question_ids[5]`
- **binding** — Spill purpose/rights/storage.
  `solution.composition_contracts[3]`
- **binding** — Spill storage/right/GC receipts.
  `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
