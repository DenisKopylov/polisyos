# GYD-23.slice0-terminal-voi — Сохранить Slice-0 BIND/ESTIMATE/VERIFY

Группа: [G04 — Содержательный поиск политик и перенос опыта](../../groups/G04.md). Родитель: [GYD-23](../../parents/GYD-23.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Deterministic SeedTrajectoryPlanner applies registry-derived BIND/ESTIMATE/VERIFY to groundable and tourism fixtures; both persist FrontierSnapshot/SearchLedger/VOI and preserve original terminal precedence.

**Предпочтительное решение.** Wire or extend the existing planner, operation registry, Slice0FixtureManifest and §3.5.1 BudgetVector; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-23's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing planner, operation registry, Slice0FixtureManifest and §3.5.1 BudgetVector.

**Входы.** committed fixtures/registry/budget; actual measurement root; B01 grounds and exact JOINT witness only if tested

**Выход и consumer.** Both persisted fixture-path terminal and VOI records

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh canonical search consumer. Keep one bounded deterministic scope; no blanket numeric EVSI.

**Positive.** Groundable partial only at measurement-root Estimate; tourism ceiling and poor-recall route persist.

**Distinguishing negative.** Forbidden op, no root, post-Estimate or DesignCandidate cannot promote; missing root stays incomplete.

**Matched removal.** Remove root/ledger/terminal port or allow later terminal while retaining marker; consumer fails.

**Граница контекста.** Keep one bounded deterministic scope; no blanket numeric EVSI.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted original Slice-0 criteria, fixture manifest, registry and budget consumed by the actual terminal result.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-23`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — All assigned task and solution fragments describe this one bounded Slice-0 operation/terminal/VOI property, including source, paths, probes, limitations and input-resolution rule.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
