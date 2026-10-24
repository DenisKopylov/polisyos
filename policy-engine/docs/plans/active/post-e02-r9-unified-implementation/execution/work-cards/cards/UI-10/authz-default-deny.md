# UI-10.authz-default-deny — Закрыть DS1-N010 через canonical AuthzProvider

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [UI-10](../../parents/UI-10.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Existing AuthzProvider decision gates every still-required C09 protected consumer: unknown/absent/error/malformed/401/prior user/tenant switch/partial never grant; fixed PUBLIC chrome remains open.

**Предпочтительное решение.** Reuse AuthzProvider and C09 cross-surface owner set; rebind only still-required original N010 negative after accepted E02.

**Граница владельца.** UI-10 owns selected client-side closure; AuthzProvider/C09 native owners remain, DS20 HTTP authorization is separate; preserve bounded indirect-flow residual.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Current server identity evidence, AuthzProvider output, full C09a/C09b disposition and original DS1-N010 criterion.

**Выход и consumer.** Protected consumers follow resolved decision; source-bound cross-surface witness retains actual outcomes.

**Что можно готовить независимо.** Bind complete consumer denominator then test every relevant auth state; reuse prior evidence only if accepted source still qualifies it.

**Где результат соединяется с другими.** Join complete source status and same C09 witness; one sample cannot close omitted consumers.

**Positive.** Verified identity exposes only current permissions; permission-free PUBLIC chrome remains.

**Distinguishing negative.** Unknown/error/malformed/401/prior subject/tenant switch/pseudo flag never grants analyst/MFA/Clerk/high-stakes CTA.

**Matched removal.** Remove guard at one actual consumer while retaining labels: C09 witness detects unauthorized render/action.

**Граница контекста.** The C09 list is denominator, not per-surface card split; do not claim arbitrary program-flow proof.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-10`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This source field contributes to authz-default-deny's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.preferred_solution, task.deliverable.
  `task.deliverable`; `solution.preferred_solution`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2], solution.acceptance_discriminators[3], solution.acceptance_discriminators[4], task.adversarial, task.positive, task.removal.
  `task.positive`; `task.adversarial`; `task.removal`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`
- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface[0], task.surface[10], task.surface[1], task.surface[2], task.surface[3], task.surface[4], task.surface[5], task.surface[6], task.surface[7], task.surface[8], task.surface[9].
  `task.surface[0]`; `task.surface[1]`; `task.surface[2]`; `task.surface[3]`; `task.surface[4]`; `task.surface[5]`; `task.surface[6]`; `task.surface[7]`; `task.surface[8]`; `task.surface[9]`; `task.surface[10]`
- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **join** — Binds source/oracle/owner behavior or fresh consumer required by the card; parent stage remains canonical. Source selectors: task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4].
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **binding** — This source field contributes to authz-default-deny's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1], solution.deviation_triggers[2], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4].
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`
- **join** — This source field contributes to authz-default-deny's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: task.acceptance_evidence_requirements[0].
  `task.acceptance_evidence_requirements[0]`
- **execute** — Advances the same native owner result; exact path/lease resolves at P0. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.input_resolution_rule, solution.inputs_to_resolve[0], solution.inputs_to_resolve[1].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
