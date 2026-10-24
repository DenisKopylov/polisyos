# DEB-03.private-reachability — Закрыть класс private-name reach

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-03](../../parents/DEB-03.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every production cross-module private import, function-local import and private-attribute edge is routed through an owner-approved supported boundary or retained as an explicit unresolved dynamic limitation.

**Предпочтительное решение.** Extend existing architecture/import tooling and package contracts to enumerate both import and attribute edges, then repair at canonical owner boundaries.

**Граница владельца.** Canonical module owners decide supported entrypoints; quality tooling measures the complete accepted production-source denominator. Use native exact-path lease family; exact paths unresolved until E02.

**Входы.** Accepted source tree; complete production import/attribute reach set; owner decisions for each true boundary and any actual downstream consumer.

**Выход и consumer.** Recomputed private-reach inventory with explicit reviewed boundary or bounded unresolved dynamic case.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh tools/quality/validation/check_package_import_gates.py and architecture import consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Every production cross-module private import, function-local import and private-attribute edge is routed through an owner-approved supported boundary or retained as an explicit unresolved dynamic limitation.

**Distinguishing negative.** A sibling/function-local private import or private attribute must be found even when import-only markers stay green; unresolved dynamic edges cannot be reported closed.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Every production cross-module private import, function-local import and private-attribute edge is routed through an owner-approved supported boundary or retained as an explicit unresolved dynamic limitation.

**Граница контекста.** This card closes private reachability; it does not close public release-fragment API review.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-03 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DEB-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — These fragments concern production private imports/attributes, canonical boundaries, consumers and complete reach enumeration.
  `task.adversarial`; `task.acceptance_evidence_requirements[0]`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
