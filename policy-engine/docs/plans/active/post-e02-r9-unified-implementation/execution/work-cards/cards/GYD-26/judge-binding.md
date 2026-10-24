# GYD-26.judge-binding — Привязать C2 verdict к реальному judge output

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-26](../../parents/GYD-26.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For the exact governed input, verdict binds actual judge producer/run, output bytes/digest and rule version; downstream arbitration/causal-graph reader consumes it as candidate evidence only.

**Предпочтительное решение.** Wire or extend the existing C2 binding plus RunNormativeArbitrationNode and causal graph consumer; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-26's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing C2 binding plus RunNormativeArbitrationNode and causal graph consumer.

**Входы.** exact governed input/content; actual judge output/run/version; accepted rule and consumer contract

**Выход и consumer.** Persisted input/output-bound verdict receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh arbitration and causal-graph consumer. Identity binding proves only identity; factual validity and authority remain separate.

**Positive.** Actual output for exact input changes the downstream candidate verdict.

**Distinguishing negative.** LLM consensus, wrong/stale output, missing bytes or marker-only promotion is no evidence.

**Matched removal.** Delete output/binding while keeping status/name/promotion marker; consumer refuses.

**Граница контекста.** Identity binding proves only identity; factual validity and authority remain separate.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted C2 input criterion/rule version consumed by the actual output binding.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-26`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Task criterion and common acceptance/companions require actual-input verdict bound and read through the existing consumer.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **join** — Question slice bundles exact output binding, identity-only positive, LLM-authority adversary and marker-preserving removal; all resolve through this actual consumer.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **execute** — Preferred solution plus steps bind actual input/output/run/version, persist content, verify bytes at consumer and probe deletion/wrong/stale/removed bindings.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — New judge versions need typed contracts; missing output stays unresolved and no judge_passed fallback or candidate-to-authority transition is added.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **execute** — Real exact-input output, marker-preserving deletion, unresolved/version invalidation and accepted source classification determine the receipt.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`
- **execute** — The actual consumer binds the candidate judge input and output receipt; agreement or identity cannot promote LLM output to authority.
  `task.r19_extension.question_slices[0]` (`R18-D21-Q01`); `task.r19_extension.question_ids[0]` (`R18-D21-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
