# OPS-08.aggregate-cap — Держать общий предел по всем живым аллокациям

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-08](../../parents/OPS-08.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every selected API/worker/process class and still-live shared allocation fits one enforceable aggregate host bound plus the measured OS/control/restore reserve; capacity is released only when actually free or transferred.

**Предпочтительное решение.** Consume LIF-06’s single native admission contract and extend the selected host enforcement adapter (cgroup/native controls, scratch quota). Reserve atomically for all processes and retain shared-cache/mapped-file/IPC charges through actual allocation lifetime; no ControlPlaneStore scheduler.

**Граница владельца.** OPS-08 owner operates only resource-family lease `resource:host/{host}/memory-disk`; LIF-06 owns the semantic admission contract and canonical reservation owner. Resolve exact runtime/profile write scope and any shared control-store lease after E02 rebind; per-label path separation proves no non-overlap.

**Входы.** LIF-06 shared resource admission and live reservations; OPS-04 actual host process classes/worker pool; Host platform controls and full active/shared allocation census; OPS-08 selected profile control/restore reserve

**Выход и consumer.** Atomic aggregate admission/defer/refusal and durable charge/reservation state in the existing LIF-06 owner; fresh runtime admission consumer sees a truthful result.

**Что можно готовить независимо.** Qualify/use only inside an already enforceable finite envelope; absent hard control or reliable process census, refuse protected work. A new class may not run unbounded just to measure itself.

**Где результат соединяется с другими.** LIF-06 emits eligibility and owns admission; OPS-08 enforces physical control and measured reserve. Completion/termination frees private resources only; shared allocation transfers require reconciliation. OPS-07 spend and per-tenant quota remain separate.

**Positive.** Concurrent processes, retries, scratch and shared allocation remain under cap while control/restore reserve remains usable; proven released allocation becomes available exactly once.

**Distinguishing negative.** Per-process semaphore multiplication, OOM, shared scratch exhaustion, stale process census, timeout or duplicate transfer cannot silently overcommit or release a still-live allocation.

**Matched removal.** Remove shared admission or allocation-lifetime reconciliation but retain process-limit/completion markers; multi-process and 60/100→50/100 saturation discriminators fail.

**Граница контекста.** One physical cap with reservation lifetime is one native mechanism. No new scheduler, queue, per-object memory tracker or universal host platform; cgroup/container labels alone are not evidence. P27/P31/P37/P38 enforce one owner and real cap.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: All writers/consumers use the accepted source and task-scoped rebind; preserve parent dispatch, not a new all-task edge.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Consume the actual runtime process/worker classes, not agent/reviewer concurrency or a guessed process census.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Use the single native aggregate admission/eligibility owner and actual usage receipt; no second shared ledger.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-08.class-envelope](../../cards/OPS-08/class-envelope.md) | For a production/duty hard-admission claim on a selected measured workload/process class; no G05 efficiency or custody-duty outcome is needed to build the base enforcement mechanism. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for aggregate-cap; selectors task.rollback, task.migration, solution.free_grow.extension_boundary, solution.migration_and_rollback, solution.composition_contracts[4], solution.deviation_triggers[1] remain load-bearing.
  `task.rollback`; `task.migration`; `solution.free_grow.extension_boundary`; `solution.migration_and_rollback`; `solution.composition_contracts[4]`; `solution.deviation_triggers[1]`
- **execute** — Direct result/preferred path for aggregate-cap; selectors task.deliverable, solution.implementation_steps[2], solution.implementation_steps[3], solution.implementation_steps[5] name the work and native owner seam.
  `task.deliverable`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[5]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for aggregate-cap; selectors task.adversarial, task.removal, task.acceptance_steps[5], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[4] are checked at its actual reader/sink.
  `task.adversarial`; `task.removal`; `task.acceptance_steps[5]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[4]`

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — Enforce one physical aggregate host bound and retain charges for still-live shared allocations. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[1]` — Supply the single enforceable physical cap and live allocation lifetime. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Enforce the shared host capacity across processes and concurrent portfolio work. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[3]` — Enforce the physical shared cap; this is not a duty scheduler or fairness owner. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Enforce the measured physical limit and disable auto-selection when a hard cap/verifier is absent. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[6]` — Account for actual host support reserve in the physical cap, without turning this into a universal environmental metric. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
