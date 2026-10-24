# DEB-14.scope-ruling-currentness — Провести scope ruling через canonical currentness

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-14](../../parents/DEB-14.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Source-bound one-plane scope ruling persists through LIF-02 canonical lifecycle/head writer and appears in a fresh UI-19 governed projection; candidate stays non-authoritative.

**Предпочтительное решение.** Reuse core/contracts/scope_adjudication.py::ScopeAdjudicationCandidate, identity/custody rules, LIF-02 and UI-19; implement one source-bound producer and lifecycle vertical.

**Граница владельца.** Scope-ruling owner creates candidate/ruling; LIF-02 alone writes canonical currentness/head and UI-19 projects. No second head writer or institution service. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Accepted source/one-plane predicate, existing scope-ruling contract, LIF-01 qualification where required, LIF-02 writer and UI-19 interface.; UI-19 actual fresh governed-projection acceptance is composed after LIF-02 persistence; it does not gate independent preparation.

**Выход и consumer.** Persisted scoped ruling with provenance, validity and currentness plus fresh UI-19 projection; currently contract_only until wired.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh UI-19 governed projection consumer.; composition is limited to this property and the exact original scope.

**Positive.** Для source-bound, independently reconciled single-plane predicates четыре кейса дают: отсутствие делает наш claim ложным → own; внешний результат меняет validity → integrate; меняется только отвечающий за claim → observe; иначе → out_of_scope. Admitted ruling сохраняется через единственный LIF-02 writer, изменение source/rule time вызывает reissue/limitation, а свежий UI-19 projection показывает currentness; candidate остаётся non-authoritative.

**Distinguishing negative.** Смешанные planes, unresolved/consumer-asserted basis или только `ScopeAdjudicationCandidate` с `authority_effect=none` не меняют authority head; неизвестное scope остаётся явным candidate limitation.

**Matched removal.** Reconciliation probe (existing source-resolution/content-bind/provenance verifier and LIF-02 admission remain enabled): replace the predicate source content digest while preserving signed/`admitted` markers and the ruling. The verifier must detect that the ruling no longer resolves to that source fact; the fresh LIF-02 reader rejects it and UI-19 does not show it as a current admitted claim.

**Граница контекста.** One vertical sequences producer -> LIF-02 -> UI-19; candidate remains non-authoritative and native lease stays singular.

## Первые действия и передача

1. Составить predicate ledger по каждому source fact: одна plane, source/content binding, valid/known time, rule version и P37 basis label (`recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied` или `not_established`).
2. Связать существующие candidate/evidence objects с фактическим producer, persistence record, LIF-02 head writer и UI-19 read path; отметить evidence для каждого перехода и отсутствующее ребро.
3. Подготовить четыре single-plane cases по ратифицированным исходам own/integrate/observe/out_of_scope и отдельный mixed-plane decomposition; неизвестные predicate оставить candidate limitation.

**Ответственность и handoff.** Четырёхстороннее правило и его source version уже ратифицированы: не добавлять authority, gate или appointment. Внешнее evidence требуется только для конкретной внешней функции; resolver, lifecycle bridge и projection — внутренняя работа.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-14 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-14 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-14 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [UI-19.claim-currentness](../../cards/UI-19/claim-currentness.md) | `acceptance:composition`: Compose the actual fresh UI-19 governed projection acceptance after persisted source-bound ruling and LIF-02 canonical currentness; candidate remains non-authoritative and this adds no start gate. Machine refs: `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/107/acceptance_dependencies/0`; supplier task `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/66`; declared native owner paths `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/66/owner_paths`. The canonical task assigns no concrete output artifact path; bind the actual source/input/backend-bound result during the scoped E02 or FINAL-REVIEW rebind.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-14`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`
- **execute** — Primary accountability is DEB-14.scope-ruling-currentness (execute) for this parent’s source-defined R19 consumer slice: Record both source-bound versions and SDD scope; candidate is not a ruling, permission or waiver of active constraints. The embedded question_id R18-D23-Q01 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[0]` (`R18-D23-Q01`); `task.r19_extension.question_ids[0]` (`R18-D23-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
