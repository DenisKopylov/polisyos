# DEB-07.wdi-cost-reconciliation — Сверить WDI cost через CAP-03

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [DEB-07](../../parents/DEB-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** When a cost-sensitive WDI route is selected, DEB-07 consumes the same persisted purpose/time/variable-bound cost artifact emitted by CAP-03; it never writes cost itself.

**Предпочтительное решение.** Keep CAP-03 the sole canonical cost writer; reconcile the original row basis/allocation against its AcquisitionCostBasisRecord and actual selected route.

**Граница владельца.** CAP-03/runtime quality acquisition_planner.py owns cost schedule and write. DEB-07 reads/reconciles only; native exact-path lease family preserves one writer; exact paths unresolved until E02.

**Входы.** Conditional CAP-03 admitted cost artifact; complete route/source/variable set, purpose and time.

**Выход и consumer.** DEB-07 source-row cost basis/allocation disposition referencing CAP-03 receipt.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh selected WDI route consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: When a cost-sensitive WDI route is selected, DEB-07 consumes the same persisted purpose/time/variable-bound cost artifact emitted by CAP-03; it never writes cost itself.

**Distinguishing negative.** Missing real cost refuses costed production route; fixture hours/days, cap or test-only hypothetical cannot substitute.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: When a cost-sensitive WDI route is selected, DEB-07 consumes the same persisted purpose/time/variable-bound cost artifact emitted by CAP-03; it never writes cost itself.

**Граница контекста.** Conditional consumption link only; does not add a blanket start edge or permit DEB-07 to own costs.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-07 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `conditional_acceptance_requirements:composition`: Read the same admitted persisted CAP-03 cost receipt for selected cost-sensitive WDI route; CAP-03 remains sole writer. Consumption mapping only; canonical stage/conditionality unchanged.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: DEB-07 reconciles the original selected-WDI admitted-cost/positive-route obligation |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DEB-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — These fragments consume CAP-03 cost as sole writer and preserve conditional cost semantics.
  `solution.implementation_steps[3]`; `solution.implementation_steps[6]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
