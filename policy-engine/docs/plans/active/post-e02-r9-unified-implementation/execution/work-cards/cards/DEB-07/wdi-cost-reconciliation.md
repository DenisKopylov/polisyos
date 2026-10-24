# DEB-07.wdi-cost-reconciliation — Сверить WDI cost через CAP-03

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [DEB-07](../../parents/DEB-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** When a cost-sensitive WDI route is selected, DEB-07 consumes the same persisted purpose/time/variable-bound cost artifact emitted by CAP-03; it never writes cost itself.

**Предпочтительное решение.** Keep CAP-03 the sole canonical cost writer; reconcile the original row basis/allocation against its AcquisitionCostBasisRecord and actual selected route.

**Граница владельца.** CAP-03/runtime quality acquisition_planner.py owns cost schedule and write. DEB-07 reads/reconciles only; native exact-path lease family preserves one writer; exact paths unresolved until E02.

**Входы.** Conditional CAP-03 admitted cost artifact; complete route/source/variable set, purpose and time.

**Выход и consumer.** DEB-07 source-row cost basis/allocation disposition referencing CAP-03 receipt.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh selected WDI route consumer.; composition is limited to this property and the exact original scope.

**Positive.** Выбранный cost-sensitive WDI route потребляет тот же persisted CAP-03 artifact, привязанный к source/variables/purpose/time, а row basis/allocation сверены и прочитаны fresh consumer-ом.

**Distinguishing negative.** Без admitted real cost costed production route отказывает; fixture hours/days, cap или test-only hypothetical не становятся production basis.

**Matched removal.** Отключить resolve/binding CAP-03 receipt, оставив route/cost markers; неизменённый selected-route test с отсутствующим или иным source/time artifact должен упасть, если fixture/stale cost всё ещё принят.

**Граница контекста.** Conditional consumption link only; does not add a blanket start edge or permit DEB-07 to own costs.

## Первые действия и передача

1. Для фактически выбранного WDI route зафиксировать source, variable set, purpose/time и тот же admitted CAP-03 `AcquisitionCostBasisRecord` receipt.
2. Сверить original source-row basis/allocation с persisted receipt и route; сохранить disposition с указанием, что запись создана CAP-03.
3. В existing route consumer подать вариант без real cost и fixture-only hours/days/cap; сохранить отказ costed production route.
4. До cost disposition проверить actual connector/comparable-ingest evidence: записать dated `expert_hours/calendar_days/collection_mode` basis, предпочесть измеримые аналоги или обосновать owner estimate; paid/licensed source требует real quote/rights evidence, а не default price.

**Ответственность и handoff.** CAP-03/runtime acquisition planner — единственный cost writer. DEB-07 только читает и сверяет; selected WDI consumer принимает результат условно для выбранного маршрута.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-07 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `conditional_acceptance_requirements:composition`: Read the same admitted persisted CAP-03 cost receipt for selected cost-sensitive WDI route; CAP-03 remains sole writer. Consumption mapping only; canonical stage/conditionality unchanged.<br>Source: `task.conditional_acceptance_requirements[1]`.<br>Условия: DEB-07 reconciles the original selected-WDI admitted-cost/positive-route obligation |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments consume CAP-03 cost as sole writer and preserve conditional cost semantics.
  `solution.implementation_steps[3]`; `solution.implementation_steps[6]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
