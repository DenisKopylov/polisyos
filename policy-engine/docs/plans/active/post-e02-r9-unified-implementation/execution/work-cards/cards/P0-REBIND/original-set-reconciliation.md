# P0-REBIND.original-set-reconciliation — Reconcile every original obligation

Группа: [G00 — Вход в программу, интеграция и итоговый допуск](../../groups/G00.md). Родитель: [P0-REBIND](../../parents/P0-REBIND.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every original predicate and accepted-E02 delta has one current disposition, native owner, actual consumer/generated/test/API closure, conditional facets, stage and lease; scoped releases never imply global completion.

**Предпочтительное решение.** Keep one root-owned reconciliation journal and canonical original inventory; source-bind each predicate, owner and reader, and release completed closures only through existing scoped-readiness rules.

**Граница владельца.** Root owns reconciliation/journal; task owners retain native semantic writes and existing path leases. Parent exact-path lease family applies; exact paths unresolved until E02, so no disjointness assumption.

**Входы.** P0-ACCEPT read-back boundary; complete GY, Atlas, debt and R9 inventories; accepted-tree source/readers/generated/test/API observations and owner dispositions.

**Выход и consumer.** Append-only per-original-predicate disposition and owner/consumer closure map, with unresolved rows retained and bounded scoped release evidence.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through FINAL-FREEZE consumes the global completed reconciliation; scoped-ready receipts are read only for their exact closures.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Every original predicate and accepted-E02 delta has one current disposition, native owner, actual consumer/generated/test/API closure, conditional facets, stage and lease; scoped releases never imply global completion.

**Distinguishing negative.** A stale count, omitted predicate, duplicate semantic writer, unowned consumer or unresolved source conflict blocks the affected closure; scoped release cannot mark global completion.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Every original predicate and accepted-E02 delta has one current disposition, native owner, actual consumer/generated/test/API closure, conditional facets, stage and lease; scoped releases never imply global completion.

**Граница контекста.** One coordination card is appropriate because the journal is the sole reconciliation surface; it dispatches no product writes and creates no per-lead ledger.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical P0-REBIND source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `P0-REBIND`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.selected_binding_requirements[0]`; `task.selected_binding_requirements[1]`; `task.selected_binding_requirements[2]`; `task.selected_binding_requirements[3]`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
