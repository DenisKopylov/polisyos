# DES-03.trial-binding — Зафиксировать реальные численные испытания

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-03](../../parents/DES-03.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every executed numerical trial resolves to its exact structural branch, parameter settings/units, method/executable identity, objective/constraint basis, source/model/rule context and accepted stochastic realization/attempt lineage.

**Предпочтительное решение.** Extend the canonical Scientist hierarchical coordinator and existing BO/grid/random/multiobjective methods by suitability. Bind trial intent, selected realization or method-qualified realization set, failures, retries, costs and changed-basis reruns; keep retry/replay semantics with native owners and add no second optimizer or universal RNG/result ledger.

**Граница владельца.** One DES-03 writer spans lease families write:scientist-policy-search, write:native-search-space and write:native-multiobjective. DES-08 shares search.py and is not presumed path-disjoint. GYD-30 alone owns CompositionCertificate and GYD-31 owns ValueOuterSet; DES-03 consumes their actual outputs. Exact paths and all lease overlap resolve after E02 source rebind.

**Входы.** DES-02 actual candidate structures; native simulation/method contracts and selected case-specific objective/constraint basis.; Selected method/resource permit and, for stochastic calls, the existing native intent/trial/attempt owner’s actual accepted result and failure denominator.

**Выход и consumer.** Persisted method-qualified trials with exact basis, attempts, accepted realization/result, cost, failure/unknown state and fresh-reader refs; no score-only synthetic result.

**Что можно готовить независимо.** Method/space preparation may begin after accepted-source rebind and interface agreement. Actual execution awaits its selected profile/permit and required source/model inputs; numerical stochastic claims stay scoped to the qualified method.

**Где результат соединяется с другими.** The frontier consumer joins these trial outputs with actual GYD-30 joint results, GYD-31 value sets and selected model/scenario evidence. This card does not decide a social scalar or admissible winner.

**Positive.** A mixed structural/parameter case produces real trials; an interrupted same-intent call resolves one accepted realization set with late/duplicate attempts retained but not double-counted.

**Distinguishing negative.** Wrong units, impossible conditional categories, stale objective direction, omitted model completion, provider-client presence without invocation, favorable retry selection or silent realization replacement cannot certify a trial.

**Matched removal.** Keep seed/result/certificate markers but remove actual method call or intent-to-realization/result binding; the independent trial/reuse oracle detects missing or double-counted execution.

**Граница контекста.** This is the single DES-03 numerical/search writer across all three native leases, not one owner per card. A future/selected trajectory is only a conditional input; DES-11 remains a separate consumer path. Native retries stay method-qualified and do not impose a generic human gate.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DES-02.hypothesis-set](../../cards/DES-02/hypothesis-set.md) | `direct:interface_agreement`: Consumes bound candidate structure as the trial branch input; DES-02 remains the candidate writer.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DES-03.frontier-composition](../../cards/DES-03/frontier-composition.md) | Consume only for the exact composition described here: The frontier consumer joins these trial outputs with actual GYD-30 joint results, GYD-31 value sets and selected model/scenario evidence. This card does not decide a social scalar or admissible winner. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DES-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — The deliverable’s actual method-bound trial producer is owned here; frontier interpretation is a separate consumer.
  `task.deliverable`
- **execute** — R16 structural/parameter, influence and changed-basis clauses bind actual trial identity and required reruns.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`
- **execute** — The preferred native method creates structural/parameter trials; the actual frontier composition is the named sibling consumer.
  `solution.preferred_solution`
- **execute** — Implementation step 0 binds the actual trial identity/selected method; named suppliers retain their own artifact owners.
  `solution.implementation_steps[0]`
- **execute** — Implementation step 1 binds the actual trial identity/selected method; named suppliers retain their own artifact owners.
  `solution.implementation_steps[1]`
- **binding** — Method/space registration and selected permit control actual trial execution; no second scheduler is introduced.
  `solution.free_grow.data_or_config_growth`
- **binding** — Stochastic intent-to-realization/attempt lineage is part of actual trial persistence; no extra ledger or global lock is added.
  `solution.composition_contracts[2]`
- **join** — The stochastic retry/late-completion discriminator is trial identity and accepted-result binding; old/duplicate completions remain dependent attempts, not new evidence.
  `solution.acceptance_discriminators[3]`
- **execute** — Bind actual structural-proposal trials; structure is not a policy weight.
  `task.r19_extension.question_slices[2]` (`R18-D08-Q02`); `task.r19_extension.question_ids[2]` (`R18-D08-Q02`)
- **execute** — Bind actual outcomes/costs separately from policy choice.
  `task.r19_extension.question_slices[3]` (`R18-D08-Q03`); `task.r19_extension.question_ids[3]` (`R18-D08-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
