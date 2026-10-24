# LIF-04.effect_recovery — Восстановить uncertain provider effect

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [LIF-04](../../parents/LIF-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Stable intent/request digest reconciles attempts to one effect; unknown differs from success/cancel/unavailable.

**Предпочтительное решение.** Extend RuntimeOperationIntent/ControlPlaneStore: persist identity, reconcile provider receipts, commit outcome/event and cancel fence.

**Граница владельца.** `write:runtime-duty`,`resource:control/{cell}/outbox`; provider/OPS are evidence, no second scheduler.

**Входы.** Action/actor/digest/grants; provider receipt/window; OPS identity; control store.

**Выход и consumer.** Persisted effect state to runtime status/audit reader.

**Что можно готовить независимо.** No trial identity.

**Где результат соединяется с другими.** Provider receipt/retry reconciles at the runtime status reader; compose duty only when this selected effect is the protected action of an admitted service duty.

**Positive.** Known effect maps one result; valid retry keeps identity.

**Distinguishing negative.** Lost reply, cancel race, old worker or wrong receipt is not success.

**Matched removal.** Remove reconciliation/fence but retain IDs; false stop/repeat fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-04.durable_service_commitment](../../cards/LIF-04/durable_service_commitment.md) | Only when this provider effect is the selected protected action for an admitted duty; ordinary effects recover without a duty commitment or duty wait. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Effect intent/receipts, positive/adversarial/removal and status.
  `task.deliverable`; `task.positive[0]`; `task.positive[1]`; `task.adversarial[0]`; `task.removal[0]`; `task.removal[1]`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **execute** — R16 effect/cancel.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`
- **execute** — Lost/doubled effect and removal.
  `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — Existing control store, identity, receipts, migration and atomic key.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`
- **execute** — Effect and canonical key probes.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`
- **binding** — Provider evidence and rollback.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`
- **binding** — Current grants; LIF05 rights owner.
  `solution.inputs_to_resolve[2]`
- **execute** — task.r19_extension.question_slices[0] crosswalks by actual value to question_ids[0]. Reconciles provider attempt/cancel/effect on the same permit; expiry alone cannot terminate an uncertain effect.
  `task.r19_extension.question_slices[0]` (`R18-D16-Q01`); `task.r19_extension.question_ids[0]` (`R18-D16-Q01`)
- **execute** — task.r19_extension.question_slices[1] crosswalks by actual value to question_ids[1]. Proves monotonic attempt across exact restore or refuses resume/reclaim, preserving cancel/effect recovery.
  `task.r19_extension.question_slices[1]` (`R18-D16-Q02`); `task.r19_extension.question_ids[1]` (`R18-D16-Q02`)
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[2]. Keeps attempts, provider receipts and cancellation distinct across rollout so retry follows reconciliation.
  `task.r19_extension.question_slices[2]` (`R18-D17-Q02`); `task.r19_extension.question_ids[2]` (`R18-D17-Q02`)
- **execute** — task.r19_extension.question_slices[3] crosswalks by actual value to question_ids[3]. Reconciles a possibly accepted remote effect before emergency retry; unknown is not success or safe retry.
  `task.r19_extension.question_slices[3]` (`R18-D17-Q05`); `task.r19_extension.question_ids[3]` (`R18-D17-Q05`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
