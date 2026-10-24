# DEB-07.gap-case-union — Сохранить GapAcquisitionCase у INT-R2

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [DEB-07](../../parents/DEB-07.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The admitted GapAcquisitionCase union matches INT-R2 ratified semantics and the real consumer; DEB-07 does not create a parallel case owner.

**Предпочтительное решение.** Use the existing INT-R2 ratification and Foundry requirements algebra; route open meaning back to the competent owner.

**Граница владельца.** INT-R2 ratification owner controls the union; DEB-07 consumes the accepted interface only. Native exact-path lease family; paths unresolved until E02.

**Входы.** Current case variants, INT-R2 ratification and real consumer contract.; Conditional UI-06 actual fresh value/uncertainty observation is consumed only when the selected INT-R2 meaning is projected; typed unknown/incomparable is preserved.

**Выход и consumer.** Owner-bound union/interface disposition and evidence of actual consuming path.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh INT-R2/Foundry case consumer.; composition is limited to this property and the exact original scope.

**Positive.** Все текущие ratified `GapAcquisitionCase` variants совпадают с INT-R2 semantics и проходят существующий реальный consumer; DEB-07 потребляет интерфейс и не вводит параллельного owner.

**Distinguishing negative.** Одних labels или нового unratified variant недостаточно: consumer оставляет его unknown/refused; DEB-13 metric basis не используется для заполнения union.

**Matched removal.** В reconciliation receipt удалить или исказить source-bound INT-R2 ref для одного variant, сохранив `complete` marker; неизменённый union-vs-ratification test должен упасть, если потерянный variant остаётся accepted.

**Граница контекста.** Case-union semantics are not the DS15 bundle producer and do not create a new case owner.

## Первые действия и передача

1. Составить current case-variant set и выписать для каждого `GapAcquisitionCase` discriminant, original INT-R2 ratification ref и принятое meaning.
2. Через existing Foundry requirements consumer сохранить outcome каждого variant; отдельно записать unknown/incomparable и отсутствующие ratification refs.
3. В reconciliation записать границу DEB-13 metric formula/decision basis, чтобы case union не присваивал этот ownership.

**Ответственность и handoff.** INT-R2 ratification owner владеет union; DEB-07 только потребляет принятую форму. DEB-13 отдельно владеет metric formula/decision basis.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-07 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [UI-06.value-grammar](../../cards/UI-06/value-grammar.md) | `conditional_acceptance_requirements:composition`: Only when the selected CORR/INT-R2 meaning is consumed by UI-06, compose the actual fresh UI-06 value/uncertainty observation with DEB-07 source-obligation acceptance; unknown/incomparable remains typed. Pinned-interface preparation may proceed; no blanket start edge. Machine refs: `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/96/conditional_acceptance_requirements/0`; supplier task `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/53`; declared native owner paths `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/53/owner_paths`. The canonical task assigns no concrete output artifact path; bind the actual source/input/backend-bound result during the scoped E02 or FINAL-REVIEW rebind.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: The selected CORR/INT-R2 meaning is consumed by the UI-06 value/uncertainty projection |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This fragment preserves INT-R2 ratification of the existing GapAcquisitionCase union and the separate DEB-13 metric owner.
  `solution.implementation_steps[5]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
