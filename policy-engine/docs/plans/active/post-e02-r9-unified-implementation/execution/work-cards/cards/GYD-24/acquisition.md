# GYD-24.acquisition — Связать RequiredDataSpec→DataNeedSpec→ACQUIRE

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [GYD-24](../../parents/GYD-24.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Pinned missing distribution resolves to permitted real fetch or exact rung-7 acquisition_required with cost and VOI bound.

**Предпочтительное решение.** Wire or extend the existing RequiredDataSpec, DataNeedSpec and ACQUIRE owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-24's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing RequiredDataSpec, DataNeedSpec and ACQUIRE owners.

**Входы.** complete applicability receipt; actual missing distribution; permitted fetch or owner cost/VOI basis

**Выход и consumer.** Persisted acquisition result or typed costed exit

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh search terminal consumer. Acquisition is sequenced after full applicability.

**Positive.** Real fetch or exact costed rung-7 exit closes the gap.

**Distinguishing negative.** Premature fetch, unbound cost or unknown connector stays limited.

**Matched removal.** Remove facet/connector/cost binding while keeping status; real reader refuses.

**Граница контекста.** Acquisition is sequenced after full applicability.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Composition output (не start gate) [GYD-24.applicability](../../cards/GYD-24/applicability.md) | Consume only for the exact composition described here: Fresh consumer: fresh search terminal consumer. Acquisition is sequenced after full applicability. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-24`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — End-to-end task outcome and common acceptance/companions close at the actual fetch-or-costed-exit result.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **execute** — Resolve the missing distribution or show refusal on omitted facet/connector, premature fetch and unbound cost.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Bound declared set, unsupported connector and exact gap remain explicit under existing planner/spec owners.
  `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`
- **binding** — ACQUIRE binds distribution, cost and VOI.
  `solution.composition_contracts[1]`
- **binding** — Close only on real acquisition/exact costed exit; source changes version/rebind consumers.
  `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
