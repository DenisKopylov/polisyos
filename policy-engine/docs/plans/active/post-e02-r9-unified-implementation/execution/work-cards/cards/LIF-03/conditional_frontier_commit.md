# LIF-03.conditional_frontier_commit — Условно продвинуть sealed frontier

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [LIF-03](../../parents/LIF-03.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Verified receipt advances partition only if expected prior root and active attempt match; conflict retains prior frontier.

**Предпочтительное решение.** Extend Fabric CursorStore conditional update; CAP receipt, artifact root and OPS persistence remain suppliers.

**Граница владельца.** Leases `write:cursor-store`,`resource:cursor/{connector}/{partition}/{incarnation}`; exact E02 call path unknown.

**Входы.** CAP receipt/cut, ArtifactRef/root/durability, OPS profile, attempt and prior frontier.

**Выход и consumer.** Persisted cursor/head read by ingestion progress and artifact reader.

**Что можно готовить независимо.** One cohesive cursor property.

**Где результат соединяется с другими.** Without continuity retain bounded partial/historical.

**Positive.** Fresh reader sees verified root; sparse semantics adapter-defined.

**Distinguishing negative.** A-after-B, ABA, crash, missing child or 304 without body retains old frontier.

**Matched removal.** Remove expected root/representation binding while markers stay; gate fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root E02 stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Commit fence, receipt, sparse semantics, adversarial/removal and surface.
  `task.deliverable`; `task.positive[0]`; `task.positive[1]`; `task.adversarial[0]`; `task.removal[0]`; `task.removal[1]`; `task.surface`; `task.rollback`; `task.migration`
- **execute** — CAP02 receipt to LIF09.
  `task.acceptance_evidence_requirements[0]`
- **execute** — R18-D15-Q02 cursor prior-root and ID.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_ids[0]`
- **execute** — CursorStore, capture/stage/reconcile, 304, profiles and discriminators.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
