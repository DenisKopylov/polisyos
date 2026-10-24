# P0-REBIND.original-set-reconciliation — Reconcile every original obligation

Группа: [G00 — Вход в программу, интеграция и итоговый допуск](../../groups/G00.md). Родитель: [P0-REBIND](../../parents/P0-REBIND.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every original predicate and accepted-E02 delta has one current disposition, native owner, actual consumer/generated/test/API closure, conditional facets, stage and lease; scoped releases never imply global completion.

**Предпочтительное решение.** Keep one root-owned reconciliation journal and canonical original inventory; source-bind each predicate, owner and reader, and release completed closures only through existing scoped-readiness rules.

**Граница владельца.** Root owns reconciliation/journal; task owners retain native semantic writes and existing path leases. Parent exact-path lease family applies; exact paths unresolved until E02, so no disjointness assumption.

**Входы.** P0-ACCEPT read-back boundary; complete GY, Atlas, debt and R9 inventories; accepted-tree source/readers/generated/test/API observations and owner dispositions.

**Выход и consumer.** Append-only per-original-predicate disposition and owner/consumer closure map, with unresolved rows retained and bounded scoped release evidence.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through FINAL-FREEZE consumes the global completed reconciliation; scoped-ready receipts are read only for their exact closures.; composition is limited to this property and the exact original scope.

**Positive.** Every original predicate and accepted-source delta has a current route, one canonical semantic owner or competent disposition, its actual consumer/companions, stage and lease; scoped releases preserve unresolved rows and do not claim global completion.

**Distinguishing negative.** An omitted or stale predicate, duplicate semantic writer, unresolved source conflict, or unknown affected consumer blocks that affected closure; unrelated, disjoint reconciliation may continue.

**Matched removal.** Remove one source-obligation binding while retaining counts and checklist labels; the existing reconciliation must identify the missing original and withhold only the affected closure.

**Граница контекста.** One coordination card is appropriate because the journal is the sole reconciliation surface; it dispatches no product writes and creates no per-lead ledger.

## Первые действия и передача

1. Fix the reconciliation denominator to the canonical GY, Atlas, debt, and R9 inventories and source versions; retain historical dispositions and explicit source conflicts.
2. For each current original predicate and accepted-E02 delta, bind the native semantic owner, actual readers, generated/test/API companions, selected conditional suppliers and consumers, stage, and exact normalized leases; distinguish preparation, readiness, composition, execution permission, and original disposition.
3. Read back and release only complete affected closures through the existing root journal while keeping one global pending map; complete all original routes before FINAL-FREEZE.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical P0-REBIND source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `P0-REBIND`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.selected_binding_requirements[0]`; `task.selected_binding_requirements[1]`; `task.selected_binding_requirements[2]`; `task.selected_binding_requirements[3]`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
