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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume use semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Remove actual lineage edge.
  `task.removal[0]`
- **execute** — R14 context/memory/selection influence.
  `task.r14_extension.requirement`
- **execute** — R15 model/study influence and tests.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — R16 positive/negative/membership/selection/executable reads.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`
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
- **execute** — task.r19_extension.question_slices[0] crosswalks by actual value to question_ids[0]. Mapping/version/weights are computational parents whose correction must reissue affected claims.
  `task.r19_extension.question_slices[0]` (`R18-D02-Q01`); `task.r19_extension.question_ids[0]` (`R18-D02-Q01`)
- **execute** — task.r19_extension.question_slices[1] crosswalks by actual value to question_ids[1]. Tracks linkage-version influence and denominator/result uncertainty, not target identity by count.
  `task.r19_extension.question_slices[1]` (`R18-D02-Q02`); `task.r19_extension.question_ids[1]` (`R18-D02-Q02`)
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[2]. Calendar adapter/correction is temporal computational influence; old-period provenance must not use latest rules.
  `task.r19_extension.question_slices[2]` (`R18-D02-Q03`); `task.r19_extension.question_ids[2]` (`R18-D02-Q03`)
- **execute** — task.r19_extension.question_slices[3] crosswalks by actual value to question_ids[3]. Boundary vintage, auxiliary data and estimator are basis lineage; aggregate labels cannot hide changed subgroup inputs.
  `task.r19_extension.question_slices[3]` (`R18-D02-Q04`); `task.r19_extension.question_ids[3]` (`R18-D02-Q04`)
- **execute** — task.r19_extension.question_slices[4] crosswalks by actual value to question_ids[11]. Lifecycle artifact/incarnation membership is an influence parent; preserve historical mapping for affected claims.
  `task.r19_extension.question_slices[4]` (`R18-D15-Q01`); `task.r19_extension.question_ids[11]` (`R18-D15-Q01`)
- **execute** — task.r19_extension.question_slices[5] crosswalks by actual value to question_ids[4]. Owns executable source/selection/model/method influence and unresolved reads, not only source currentness.
  `task.r19_extension.question_slices[5]` (`R18-D07-Q02`); `task.r19_extension.question_ids[4]` (`R18-D07-Q02`)
- **execute** — task.r19_extension.question_slices[6] crosswalks by actual value to question_ids[5]. Binds source/model/selection/memory basis for computational reuse; rights/current-use admission remains separate.
  `task.r19_extension.question_slices[6]` (`R18-D08-Q05`); `task.r19_extension.question_ids[5]` (`R18-D08-Q05`)
- **execute** — task.r19_extension.question_slices[8] crosswalks by actual value to question_ids[7]. Per-call context/tools are computational identity even under shared profile; qualification is not a cache key.
  `task.r19_extension.question_slices[8]` (`R18-D11-Q01`); `task.r19_extension.question_ids[7]` (`R18-D11-Q01`)
- **execute** — task.r19_extension.question_slices[9] crosswalks by actual value to question_ids[8]. Resolves execution/model descendants and dynamic lineage gaps; this is computational influence before rights-use admission.
  `task.r19_extension.question_slices[9]` (`R18-D14-Q02`); `task.r19_extension.question_ids[8]` (`R18-D14-Q02`)
- **execute** — task.r19_extension.question_slices[12] crosswalks by actual value to question_ids[12]. Tracks changed executable/model influence separately from the current-use right to consume its result.
  `task.r19_extension.question_slices[12]` (`R18-D17-Q01`); `task.r19_extension.question_ids[12]` (`R18-D17-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
