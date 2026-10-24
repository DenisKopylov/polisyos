# LIF-07.computational_influence — Связать influence в lineage

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-07](../../parents/LIF-07.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Derivative/cache binds complete computational/semantic/selection/executable/dynamic-read parents; unknown closure misses/limits.

**Предпочтительное решение.** Extend ArtifactManifest/InputRef/ArtifactLineageGraph; conservative miss before incremental closure.

**Граница владельца.** `write:derived-lineage/{owner}`; LIF01 use, LIF02 currentness, LIF05 rights, model/method owner learning.

**Входы.** Artifact/profile/producer, input roles, model/training/selection/method and source cut if current.

**Выход и consumer.** Persisted role-qualified lineage/cache identity.

**Что можно готовить независимо.** Graph is not permission/currentness/independence.

**Где результат соединяется с другими.** Unknown input is conservative miss.

**Positive.** Exact basis reuse; changed basis recomputes affected.

**Distinguishing negative.** Bytes/topology/no-hit as equivalence/independence.

**Matched removal.** Remove actual parent, keep labels; miss/refuse.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume use semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Remove actual lineage edge.
  `task.removal[0]`
- **execute** — R14 context/memory/selection influence.
  `task.r14_extension.requirement`
- **execute** — R15 model/study influence and tests.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — R16 positive/negative/membership/selection/executable reads.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`
- **execute** — R18 mapping/linkage/calendar/boundary/lifecycle and basis sources.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[5]`; `task.r19_extension.question_slices[6]`
- **execute** — Per-call context and model/execution influence.
  `task.r19_extension.question_slices[8]`; `task.r19_extension.question_slices[9]`
- **execute** — Executable and question IDs mapped to computational slices; U087/U090/U091 are current-use IDs.
  `task.r19_extension.question_slices[12]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[6]`; `task.r19_extension.question_ids[8]`; `task.r19_extension.question_ids[9]`; `task.r19_extension.question_ids[12]`
- **execute** — Native graph, roles, closure, invalidation and alternatives.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`
- **binding** — Generic profiles, closure and bounds.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **binding** — Exact artifact/role/predicate identity.
  `solution.composition_contracts[0]`
- **execute** — Affected invalidation/incomplete closure.
  `solution.composition_contracts[2]`
- **execute** — Exact parent positive.
  `solution.acceptance_discriminators[0]`
- **execute** — Unknown read/stale reverse lineage.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **binding** — CAS/model/training/method inputs, not supplier appointments.
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
