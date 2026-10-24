# OPS-04.external-runner — Запускать внешний worker через действующий lease

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-04](../../parents/OPS-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An authorized durable job claimed by the supervised process has one valid existing lease generation and a fresh API reader observes persisted outcome; an effect without receipt stays unknown.

**Предпочтительное решение.** Add the proposed external entrypoint around ControlWorker, ControlPlaneStore and the existing handler registry. Reuse lease, heartbeat, renewal, cancellation, receipt and authorization lifecycle; use the selected platform supervisor only. No second queue, worker scheduler or retry ledger.

**Граница владельца.** Only the runner entrypoint is writable under canonical lease family `write:external-runner-entrypoint`; current worker/store/handler paths are read-only mechanism anchors. Exact proposed path, imports and overlap are resolved after E02 rebind; no writer is assigned to supplier paths.

**Входы.** OPS-01 selected worker/process profile; OPS-03 actual worker readiness signals; LIF-04 durable job intent, lease generation and attempt outcome; Selected handler/source idempotency or positive effect-reconciliation evidence; OPS-05 supported directional reader/writer/schema/rule matrix when rollout requires it

**Выход и consumer.** Supervised process entrypoint plus durable start/heartbeat/finish/unknown-effect receipt in existing ControlPlaneStore; fresh authorized API reader sees the persisted lifecycle state.

**Что можно готовить независимо.** The process entrypoint and supervisor can be prepared independently against the existing worker/store interface after scoped rebind. Protected dispatch waits for actual E02 acceptance, profile/readiness and a valid durable lease. Rollout checks consume OPS-05 direction only when independently rolling versions are selected.

**Где результат соединяется с другими.** Supervisor health, worker lease, job outcome, effect reconciliation, schema compatibility and semantic admission stay distinct. LIF-04 owns durable duty/effect semantics; OPS-05 owns supported persisted-reader directions; OPS-03 consumes live worker signals.

**Positive.** Restarted external worker shares the existing lease path and produces an outcome a fresh API reader resolves; supported mixed versions work in their actual declared direction.

**Distinguishing negative.** Absent/duplicate runner, expired lease, cancellation, crash after effect before receipt, incompatible direction or unauthorized scope cannot create false completion or blind retry.

**Matched removal.** Remove the real external runner/lease/read path while keeping service and version labels; readiness and semantic acceptance fail.

**Граница контекста.** Runner, uncertain effect and selected rollout directions are checkpoints in one durable job path, not separate queue/scheduler capabilities. P02/P07/P38: test actual lease/effect/reader behavior and the direction used.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Actual E02 acceptance and accepted-source rebind remain inherited dispatch conditions.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01.commissioning](../../cards/OPS-01/commissioning.md) | `direct:owner_readiness`: Consume the selected supervised process/profile and release pairing.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Consume the actual worker readiness signal before worker-backed admissions.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: Use the existing durable job/attempt/lease owner for claim, cancellation, terminal and unresolved-effect semantics.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-05](../../parents/OPS-05.md) | `interface_reference:reference_only_no_new_gate`: Consume direction-specific compatibility only for selected independently rolling API/worker/schema/rule profiles; do not impose a new universal rolling gate.<br>Source parent `OPS-05`: `task.deliverable`.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for external-runner; selectors task.rollback, task.migration, task.rollback_precedence, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.migration_and_rollback, solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2], solution.deviation_triggers[0], solution.deviation_triggers[1], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.input_resolution_rule remain load-bearing.
  `task.rollback`; `task.migration`; `task.rollback_precedence`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`
- **execute** — Direct result/preferred path for external-runner; selectors task.deliverable, solution.preferred_solution, solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3] name the work and native owner seam.
  `task.deliverable`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for external-runner; selectors task.positive, task.adversarial, task.removal, task.surface, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.acceptance_steps[5], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2] are checked at its actual reader/sink. Bundled subclauses: U023:{"question_id":"R18-D16-Q02","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q02","mechanism_ids":["S16-M2"],"role":"consumer"}; U024:{"question_id":"R18-D17-Q01","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q01","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"primary writer"}; U025:{"question_id":"R18-D17-Q02","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q02","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"primary writer"}.
  `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.acceptance_steps[5]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **join** — The runner consumes the existing worker/store lease and must recover the same durable owner/result after restart; OPS-04 does not add a queue or scheduler.
  `task.r19_extension.question_slices[0]` (`R18-D16-Q02`); `task.r19_extension.question_ids[0]` (`R18-D16-Q02`)
- **join** — The actual API/worker/handler version combination and operation direction are tested at the supervised runner consumer; the same FQN or a version label is insufficient.
  `task.r19_extension.question_slices[1]` (`R18-D17-Q01`); `task.r19_extension.question_ids[1]` (`R18-D17-Q01`)
- **join** — OPS-04 owns the real mixed API/worker overlap and durable job outcome during rollout; compatibility is operation- and direction-specific.
  `task.r19_extension.question_slices[2]` (`R18-D17-Q02`); `task.r19_extension.question_ids[2]` (`R18-D17-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
