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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Spill purpose/rights/storage.
  `solution.composition_contracts[3]`
- **binding** — Spill storage/right/GC receipts.
  `solution.inputs_to_resolve[2]`
- **execute** — task.r19_extension.question_slices[3] crosswalks by actual value to question_ids[3]. Ties actual verification cost/work to the exact edition and duty; material-support accounting owns the denominator.
  `task.r19_extension.question_slices[3]` (`R18-D19-Q02`); `task.r19_extension.question_ids[3]` (`R18-D19-Q02`)
- **execute** — task.r19_extension.question_slices[4] crosswalks by actual value to question_ids[4]. Reconciles physical copies/receipts to edition and scope, counting replicas and covering aggregates once.
  `task.r19_extension.question_slices[4]` (`R18-D19-Q04`); `task.r19_extension.question_ids[4]` (`R18-D19-Q04`)
- **execute** — task.r19_extension.question_slices[5] crosswalks by actual value to question_ids[5]. Binds energy to duty and a complete support inventory; missing support evidence must remain partial.
  `task.r19_extension.question_slices[5]` (`R18-D19-Q05`); `task.r19_extension.question_ids[5]` (`R18-D19-Q05`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
