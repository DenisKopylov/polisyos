# P0-ACCEPT.accepted-boundary — Read back the competent E02 acceptance

Группа: [G00 — Вход в программу, интеграция и итоговый допуск](../../groups/G00.md). Родитель: [P0-ACCEPT](../../parents/P0-ACCEPT.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only the existing competent G decision, bound to its exact accepted source, scope, inputs, backends, limitations and authority boundary, opens the named entry scope.

**Предпочтительное решение.** Use the existing G acceptance owner and decision; resolve immutable commit/tree identity and append source-qualified root evidence.

**Граница владельца.** Root owns the read-back journal only; the G owner alone issues the decision. Use the parent native exact-path lease family; exact paths remain unresolved until E02 rebind.

**Входы.** Existing G decision and its competent owner; accepted source/input/backend/profile identities.

**Выход и consumer.** Read-back acceptance record with immutable source/tree, precise admitted scope, inputs, backends, limitations, exclusions and decision provenance.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through P0-REBIND root journal consumes this exact accepted decision and opens only matched scopes.; composition is limited to this property and the exact original scope.

**Positive.** The existing competent G decision is read back against its immutable source, scope, inputs, backends, limitations, exclusions, and provenance; only scopes within that decision are opened.

**Distinguishing negative.** A topic head, local green check, assumed completion, or receipt-shaped file cannot open product implementation entry; a missing or ambiguous decision remains unresolved.

**Matched removal.** Remove the decision-to-source/scope binding while leaving planning declarations and an accepted label; the existing P0-REBIND consumer must leave entry unresolved or closed.

**Граница контекста.** One external entry decision is a coordination result, not a new PolicyOS acceptance service or leaf implementation.

## Первые действия и передача

1. Read the existing G acceptance decision and its source-qualified evidence from the competent G owner; record who issued it and the exact decision identity.
2. Resolve accepted commit/tree, exact scope, inputs, backends, limitations, exclusions, and authority boundary; record any absent or contradictory field as unresolved.
3. Compare proposed entry scopes with that recorded boundary and append only matching scopes to the existing root journal; append a rebind requirement if the accepted source or scope changes.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `P0-ACCEPT`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
