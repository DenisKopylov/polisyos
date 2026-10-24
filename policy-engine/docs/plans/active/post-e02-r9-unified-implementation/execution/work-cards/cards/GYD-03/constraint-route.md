# GYD-03.constraint-route — Реальный маршрут RequiredDataSpec к optimizer

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [GYD-03](../../parents/GYD-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A real D0/staged intake with an owner-recomputed requirement basis and admitted safety/context reaches the actual optimizer through ConstraintStore, or returns a typed refusal.

**Предпочтительное решение.** Reuse generation_cycle, RequiredDataSpec, ConstraintStoreIngestor and reconcile_method; extend their existing route and consume real D0/basis/safety evidence.

**Граница владельца.** The Foundry ConstraintStore and optimizer remain their existing owners; resolve the exact ConstraintStore file/lease at rebind. Do not add a second store or produce institutional safety/context evidence. Recompute basis from its source, not caller declarations.

**Входы.** Actual Data Forge D0/staged intake and its source-bound evidence.; Owner-recomputed RequiredDataSpec basis.; Independent EvalSafety/context evidence from its actual owner.; Actual ConstraintStore/optimizer consumer.

**Выход и consumer.** Persisted source-bound route/basis receipt or typed refusal, followed by the real optimizer run receipt.

**Что можно готовить независимо.** Rebind the accepted source and exact existing ConstraintStore interface.; Resolve the D0, basis and safety/context producers and agreed interfaces.; Run the optimizer through the actual route; remove each decisive binding for refusal proof.

**Где результат соединяется с другими.** The route joins D0, recomputed basis and independent safety/context at the optimizer; each input owner remains native. No synthetic method output.

**Positive.** A real route reaches ConstraintStore and optimizer with resolved source-bound evidence and a fresh run receipt.

**Distinguishing negative.** Missing D0, fabricated requirement basis, absent safety/context, or wrong source refuses before optimizer admission.

**Matched removal.** Remove route, content, or safety binding while preserving request/ref markers; actual optimizer consumer refuses.

**Граница контекста.** One end-to-end method route in G05. The exact ConstraintStore owner path is unresolved at the source and must be pinned; unresolved ownership is not a reason to invent a new store.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The constraint-route card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
