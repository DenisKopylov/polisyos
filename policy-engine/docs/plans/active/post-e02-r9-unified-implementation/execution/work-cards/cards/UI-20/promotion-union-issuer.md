# UI-20.promotion-union-issuer — Провести promotion variants через canonical issuer

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [UI-20](../../parents/UI-20.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every owner-defined promotion variant round-trips from canonical generated union through private issuer into DS15 with status/limitations; forged or unknown variants remain candidate-only.

**Предпочтительное решение.** Bind exact DS5 group/native owner at P0; extend canonical contract/generator and DS15 bridge; internal issuer accepts only resolved content-bound owner evidence.

**Граница владельца.** Canonical DS5 owner writes contract/generator and private issuer; UI-20 owns bound native bridge only. TypeScript private/brand is not authority. Keep semantic-owner/promotion lease.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:semantic-owner/promotion; write:runtime-api-generated-family if changed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Exact original DS5 row/group and named negative, canonical owner evidence/verifier provenance and all owner-defined variants.

**Выход и consumer.** Generated union/private issue flows to actual DS15 consumer with limitations; unhandled variant candidate-only.

**Что можно готовить независимо.** Resolve writer/negative before implementation; prepare interface after P0; retain generated-family lease.

**Где результат соединяется с другими.** Positive requires runtime resolve/content-bind/verifier provenance and fresh DS15 read; UI-17 shares lease if paths overlap.

**Positive.** All known variants round-trip through owner generator/API/issuer/consumer.

**Distinguishing negative.** Forged wire payload, public construction, novel variant or stripped limitation cannot create authority.

**Matched removal.** Bypass issuer/remove guard with labels: original DS5 negative and fresh consumer fail.

**Граница контекста.** Generator/API/issuer are one authority admission chain; no other DS12/14/18 successor rebuilt.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-20`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This source field contributes to promotion-union-issuer's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.preferred_solution, task.deliverable, task.issuer_semantics.
  `task.deliverable`; `task.issuer_semantics`; `solution.preferred_solution`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2], task.adversarial, task.positive, task.removal.
  `task.positive`; `task.adversarial`; `task.removal`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface.
  `task.surface`
- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **execute** — Advances the same native owner result; exact path/lease resolves at P0. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — This source field contributes to promotion-union-issuer's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.input_resolution_rule, solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.inputs_to_resolve[2].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
