# LIF-05.placement_restore_and_retained_use — Сверить placement, deletion и restore

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-05](../../parents/LIF-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each actual placement receives a rights/retention/existence decision against post-backup history and currentness; LIF05 does not decide physical restore enablement.

**Предпочтительное решение.** Consume the same LIF05 decision at CAS/provider/backup placements; OPS05 alone owns physical restore/quarantine/cut/continuity and enablement, consuming this per-placement rights result.

**Граница владельца.** LIF05 owns per-placement rights/retention/existence decisions; CAS owns placements/pins; OPS05 is sole physical restore/quarantine/cut/continuity/enablement owner; LIF02 currentness and LIF07 descendants keep their owners.

**Входы.** Actual placement/retained-copy inventory and OPS05 physical restore/quarantine/cut/continuity witness; post-backup rights decision/generation; LIF02 source/currentness cut; LIF07 descendant paths.

**Выход и consumer.** Persisted per-placement rights/retention/existence result and reconciliation receipt consumed by OPS05 and a fresh authorized artifact/claim reader; no second admission or physical-enable bit.

**Что можно готовить независимо.** Inventory and rights replay can prepare against agreed interfaces; actual OPS05 restore enablement remains its sole owner and joins this result at composition.

**Где результат соединяется с другими.** OPS-05 joins the per-placement rights/retention/existence result with its physical quarantine/restore cut and continuity witness before it alone enables the selected fresh protected read.

**Positive.** Every covered placement has an explicit rights/retention/existence result; OPS05 enables only after its independent physical/history reconciliation.; Lawful history remains as-of; restore cannot revive a withdrawn head.

**Distinguishing negative.** Tombstone as erasure, old restore current, foreign copy presumed gone.

**Matched removal.** Remove placement/replay with tombstone intact; reader fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Fresh currentness at sinks/restore; inventory independent.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-05.rights_decision](../../cards/LIF-05/rights_decision.md) | For each actual retained/restore placement, bind its rights decision and generation; this does not create a physical restore-admission bit or transfer OPS-05 enablement. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Restore after rights replay.
  `task.positive[1]`
- **execute** — Actual placement inventory.
  `task.migration`
- **binding** — R14 retention for prompt/cache/revisions.
  `task.r14_extension.requirement`
- **execute** — Placement inventory/post-backup rights.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **execute** — Migration/quarantine/legal history.
  `solution.migration_and_rollback`
- **binding** — CAS/OPS responsibilities.
  `solution.composition_contracts[1]`
- **execute** — Foreign scope and lawful retention per placement.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **binding** — Placement/provider/backup receipts.
  `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
