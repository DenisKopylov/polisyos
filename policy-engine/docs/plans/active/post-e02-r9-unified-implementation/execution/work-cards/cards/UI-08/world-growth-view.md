# UI-08.world-growth-view — Показать DS21 effect/world-growth с происхождением

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [UI-08](../../parents/UI-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** One read-only view projects O1 confirmatory and O3 versioned growth on one branch; cause/authority/time/version and acquisition/deployment origin remain distinct; O2 remains candidate_unverified.

**Предпочтительное решение.** Reuse governed projection/Cycle Board; consume GYD-09 and GYD-12 persisted outputs; no second causal ledger or posterior writer.

**Граница владельца.** UI-08 owns read-only view; O1/GYD-09 and O3/GYD-12 produce owner artifacts, O2 stays candidate-only; UI never writes world head/WMR.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Accepted O1 artifact, O3 branch/head and cause/time rule.

**Выход и consumer.** Persisted records project to reviewer/MACHINE/CLI/audit with distinct acquisition/deployment provenance.

**Что можно готовить независимо.** Prepare one projection contract independently; positive composition needs both source outputs.

**Где результат соединяется с другими.** Join qualified O1/O3 outputs at the selected AtlasRunDeck/reviewer browser and MACHINE/CLI/audit readouts. At E02 bind the actual browser read and source-qualified oracle; component presence alone is not a receipt, and O2 remains candidate-only.

**Positive.** All cause classes and unresolved/compound states honest; current WP-01/02 produces no posterior mutation.

**Distinguishing negative.** Protective response, unresolved cause, stale branch, candidate, or non-prediction class never becomes authority.

**Matched removal.** Remove either O1/O3 binding with markers: fresh consumer witness fails.

**Граница контекста.** No split by cause/source/transport; full matrix belongs to one branch view.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-09.o1-confirmatory-update](../../cards/GYD-09/o1-confirmatory-update.md) | `direct:interface_agreement; acceptance:composition`: Persisted O1 confirmatory effect/update with cause/profile/branch provenance.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [GYD-12](../../parents/GYD-12.md) | `direct:interface_agreement; acceptance:composition`: Persisted O3 versioned world-growth branch/head.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This source field contributes to world-growth-view's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.preferred_solution, task.deliverable.
  `task.deliverable`; `solution.preferred_solution`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2], solution.acceptance_discriminators[3], task.adversarial, task.positive, task.removal.
  `task.positive`; `task.adversarial`; `task.removal`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`
- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface[0], task.surface[1], task.surface[2].
  `task.surface[0]`; `task.surface[1]`; `task.surface[2]`
- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **join** — Binds source/oracle/owner behavior or fresh consumer required by the card; parent stage remains canonical. Source selectors: task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4].
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **binding** — This source field contributes to world-growth-view's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4].
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **execute** — Routes extension by its property into the existing currentness/rights/time/audience/evidence owner. Source selectors: task.r15_extension.adversarial, task.r15_extension.detail, task.r15_extension.positive, task.r15_extension.product_verification, task.r15_extension.quality_ref, task.r15_extension.removal, task.r15_extension.requirement, task.r15_extension.technical_profiles[0], task.r15_extension.technical_profiles[1], task.r15_extension.technical_profiles[2], task.r16_extension.adversarial, task.r16_extension.delivery_slices[0], task.r16_extension.positive, task.r16_extension.product_verification, task.r16_extension.quality_cases[0], task.r16_extension.quality_cases[1], task.r16_extension.quality_cases[2], task.r16_extension.quality_cases[3], task.r16_extension.quality_cases[4], task.r16_extension.quality_cases[5], task.r16_extension.quality_cases[6], task.r16_extension.removal, task.r16_extension.requirement.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`; `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.product_verification`; `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`; `task.r16_extension.quality_cases[5]`; `task.r16_extension.quality_cases[6]`; `task.r16_extension.product_verification`
- **binding** — Routes extension by its property into the existing currentness/rights/time/audience/evidence owner. Source selectors: task.r17_extension.adversarial, task.r17_extension.delivery_slices[0], task.r17_extension.positive, task.r17_extension.product_verification, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r17_extension.quality_cases[4], task.r17_extension.quality_cases[5], task.r17_extension.removal, task.r17_extension.requirement.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.quality_cases[5]`; `task.r17_extension.product_verification`
- **execute** — Advances the same native owner result; exact path/lease resolves at P0. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2], solution.composition_contracts[3], solution.composition_contracts[4].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.composition_contracts[4]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.input_resolution_rule, solution.inputs_to_resolve[0], solution.inputs_to_resolve[1].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
