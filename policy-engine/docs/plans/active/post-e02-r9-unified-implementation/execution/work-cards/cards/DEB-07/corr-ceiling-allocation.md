# DEB-07.corr-ceiling-allocation — Распределить CORR destination и ceiling meanings

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [DEB-07](../../parents/DEB-07.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every current CORR destination/ceiling has distinct native owner, exact meaning, producer, consumer and typed unknown/incomparable result; no historical five/five denominator is treated as current.

**Предпочтительное решение.** Preserve delivered mechanical crosswalk and route each still-open semantic proposition to its actual owner; internal missing producer becomes assigned work, not external wait.

**Граница владельца.** Team-architecture coordinates semantic allocation; destination owners define meaning and native writes. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Complete current CORR/INT-R2 destination and ceiling enumeration; owner decision for open reviewer/profile and B2 semantic producer.; Conditional UI-06 actual fresh value/uncertainty observation is consumed only when the selected CORR meaning is projected; typed unknown/incomparable is preserved.

**Выход и consumer.** Source-bound owner/path/meaning/use/producer/consumer disposition for every current destination.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh destination-specific CORR consumers.; composition is limited to this property and the exact original scope.

**Positive.** Каждый текущий source-enumerated destination/meaning имеет отдельный owner, exact use, producer и consumer; settled решения сохраняются, а открытая семантика явно остаётся proposal/open без фиктивного общего count.

**Distinguishing negative.** Неполный набор строк, label без consumer или scalarized incomparable ceilings не закрывают слот и не дают положительного общего результата.

**Matched removal.** Повредить/удалить source-bound строку одного destination при сохранённом `complete` marker; неизменённый reconciliation test должен упасть, если строка без owner/meaning/consumer всё ещё считается закрытой.

**Граница контекста.** This is meaning/owner allocation; estimand relations, cost, DS15 and case-union keep their own producers.

## Первые действия и передача

1. Из accepted source составить полный список текущих CORR/INT-R2 destinations и ceiling meanings с IDs и denominator; пометить исторические 5/5 и 4/5 как snapshots.
2. Для каждого slot заполнить source-qualified owner/path, exact meaning/use, producer, distinct consumer и settled/open disposition.
3. Сверить отдельные vocabulary rows с original meaning и consumer; для открытых B1 reviewer/profile и B2 producer записать назначенного внутреннего owner или конкретное unresolved действие вместе с первыми regime/consumer propositions.

**Ответственность и handoff.** Team-architecture координирует allocation; destination owners определяют semantics и canonical writes, их consumers читают результат. UI-06 подключается только при выбранной projection.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-07 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [UI-06.value-grammar](../../cards/UI-06/value-grammar.md) | `conditional_acceptance_requirements:composition`: Only when the selected CORR/INT-R2 meaning is consumed by UI-06, compose the actual fresh UI-06 value/uncertainty observation with DEB-07 source-obligation acceptance; unknown/incomparable remains typed. Pinned-interface preparation may proceed; no blanket start edge. Machine refs: `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/96/conditional_acceptance_requirements/0`; supplier task `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/53`; declared native owner paths `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/53/owner_paths`. The canonical task assigns no concrete output artifact path; bind the actual source/input/backend-bound result during the scoped E02 or FINAL-REVIEW rebind.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The selected CORR/INT-R2 meaning is consumed by the UI-06 value/uncertainty projection |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments enumerate current CORR/INT-R2 destination meanings, owners, consumers and non-fixed historical denominator.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
