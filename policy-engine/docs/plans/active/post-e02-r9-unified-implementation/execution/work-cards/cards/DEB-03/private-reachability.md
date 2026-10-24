# DEB-03.private-reachability — Закрыть класс private-name reach

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-03](../../parents/DEB-03.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every production cross-module private import, function-local import and private-attribute edge is routed through an owner-approved supported boundary or retained as an explicit unresolved dynamic limitation.

**Предпочтительное решение.** Extend existing architecture/import tooling and package contracts to enumerate both import and attribute edges, then repair at canonical owner boundaries.

**Граница владельца.** Canonical module owners decide supported entrypoints; quality tooling measures the complete accepted production-source denominator. Use native exact-path lease family; exact paths unresolved until E02.

**Входы.** Accepted source tree; complete production import/attribute reach set; owner decisions for each true boundary and any actual downstream consumer.

**Выход и consumer.** Recomputed private-reach inventory with explicit reviewed boundary or bounded unresolved dynamic case.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh tools/quality/validation/check_package_import_gates.py and architecture import consumer.; composition is limited to this property and the exact original scope.

**Positive.** Полный текущий census показывает, что каждый cross-module private edge либо направлен через одобренный владельцем boundary, либо явно остаётся unresolved; private reach не объявляется закрытым при dynamic residual.

**Distinguishing negative.** Добавленные function-local private import и cross-module private attribute обнаруживаются resolver даже если import-only markers зелёные; без owner route результат остаётся открытым.

**Matched removal.** Отключить attribute-edge resolution, оставив import checks и markers; неизменённый тест с `self._origins._admit_completed_execution` должен упасть, если gate пропустил edge или заявил полный зелёный boundary.

**Граница контекста.** This card closes private reachability; it does not close public release-fragment API review.

## Первые действия и передача

1. Сгенерировать полный accepted-source reach census production-файлов: module imports, function-local imports и cross-module private-attribute edges; записать roots, file types, exclusions и unresolved dynamic cases.
2. Для каждого найденного edge приложить canonical owner disposition и supported entrypoint либо оставить именованный bounded dynamic residual; не превращать список примеров в allowlist.
3. Запустить resolver на sibling/function-local private import и на `self._origins._admit_completed_execution`; сохранить результаты import-only и attribute-aware проходов.

**Ответственность и handoff.** Canonical module owners определяют entrypoints; существующий quality/architecture tooling вычисляет census и проверяет boundary. Не расширять public API ради checker.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-03 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments concern production private imports/attributes, canonical boundaries, consumers and complete reach enumeration.
  `task.adversarial`; `task.acceptance_evidence_requirements[0]`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
