# UI-05.clerk-candidate-view — Показывать G6 candidate/refusal без повышения authority

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [UI-05](../../parents/UI-05.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Clerk summary/reviewer export retains session/choice/loss refs, rejected alternatives, limitations and authoritative_for=[]; PUBLIC remains out_of_scope.

**Предпочтительное решение.** Переиспользовать G6 orchestration seam и existing Clerk components/client; loss receipt controls summary.

**Граница владельца.** UI-05 owns existing reviewer/expert projection only; G6 evidence and conditional DS9 PA2 action gate are native owners.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** G6 session/choice/loss artifact, GY-I+DS9 PA2 output for dispatched action, PA3 loss receipt/not_measured; conditional UI-13 delegation and LIF-05 disclosure.

**Выход и consumer.** Grounded view linked to source/loss/audit; missing context yields refusal state.

**Что можно готовить независимо.** Prepare on artifact/API agreement; only action or disclosure path waits on exact conditional owner output.

**Где результат соединяется с другими.** Compose conditional PA2 or rights output only where selected; no blanket action gate for passive view.

**Positive.** Candidate/refusal, rejected set, loss receipt, limitations and zero authority survive summary.

**Distinguishing negative.** Fluent text, missing audit, dropped limits, truncation or novel status never gains authority.

**Matched removal.** Remove provenance/loss join with markers: grounded presentation disappears.

**Граница контекста.** One artifact-to-Clerk consumer; role label or fluent summary is not evidence.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [UI-13.ds9-scorecard-route](../../cards/UI-13/ds9-scorecard-route.md) | `conditional_acceptance_requirements:composition`: Conditional DS9/PA2 role-purpose-TTL delegation and contestability artifact for dispatched action.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: DS14 outward agent/tool action is actually dispatched |
| Supplier [LIF-05](../../parents/LIF-05.md) | `conditional_acceptance_requirements:composition`: Conditional source-defined disclosure composition and permitted projection.<br>Source: `task.conditional_acceptance_requirements[1]`.<br>Условия: cross-projection disclosure can reconstruct a protected premise |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This source field contributes to clerk-candidate-view's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.preferred_solution, task.deliverable, task.gate_ruling, task.pa2_scope_rule.
  `task.deliverable`; `task.gate_ruling`; `task.pa2_scope_rule`; `solution.preferred_solution`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2], solution.acceptance_discriminators[3], task.adversarial, task.positive, task.removal.
  `task.positive`; `task.adversarial`; `task.removal`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`
- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface[0], task.surface[1], task.surface[2].
  `task.surface[0]`; `task.surface[1]`; `task.surface[2]`
- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **join** — Binds source/oracle/owner behavior or fresh consumer required by the card; parent stage remains canonical. Source selectors: task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4].
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **binding** — This source field contributes to clerk-candidate-view's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.r14_extension.detail, task.r14_extension.product_verification, task.r14_extension.quality_ref, task.r14_extension.requirement.
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **execute** — Advances the same native owner result; exact path/lease resolves at P0. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.input_resolution_rule, solution.inputs_to_resolve[0], solution.inputs_to_resolve[1].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
