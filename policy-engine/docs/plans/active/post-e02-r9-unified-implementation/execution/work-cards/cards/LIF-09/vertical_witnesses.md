# LIF-09.vertical_witnesses — Проверить producer-to-consumer path

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [LIF-09](../../parents/LIF-09.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Selected path exercises actual producer→persisted event/artifact→bridge→fresh reader→surface and runtime removal.

**Предпочтительное решение.** Use actual native LIF/CAP/OPS path; no mock or marker-only gate.

**Граница владельца.** Native owners stay writers; this card only verifies.

**Входы.** Frozen rows, actual receipts, fresh surface, independent oracle.

**Выход и consumer.** Persisted positive/negative/removal outputs.

**Что можно готовить независимо.** Prepare the selected native route, oracle and adversarial/removal probes independently. Actual selected-row execution consumes frozen accepted rows and exact source/input/backend identities from freeze_and_readiness; owner closure is not a prerequisite for test design or isolated witness preparation.

**Где результат соединяется с другими.** Exercise only active selected rows against the frozen identity/denominator; final review remains the canonical FINAL-REVIEW stage.

**Positive.** Useful behavior/refusal traverses chain.

**Distinguishing negative.** Mock supplier or removed property leaves green.

**Matched removal.** Delete runtime property keeping markers; gate fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves canonical accepted-source stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Freeze use scope, exercise relation, bind result.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Exercise currentness/duty reader, bind receipt.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-03.conditional_frontier_commit](../../cards/LIF-03/conditional_frontier_commit.md) | `direct:owner_readiness`: Exercise cursor receipt and bind.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: Exercise selected effect/duty.<br>Source: `task.depends_on[4]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:owner_readiness`: Exercise rights/sink/placement.<br>Source: `task.depends_on[5]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Freeze and exercise measured profile.<br>Source: `task.depends_on[6]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-07](../../parents/LIF-07.md) | `direct:owner_readiness`: Exercise selected lineage/current-use.<br>Source: `task.depends_on[7]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-08](../../parents/LIF-08.md) | `direct:owner_readiness`: Freeze source/reader matrix and exercise second source.<br>Source: `task.depends_on[8]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-05](../../parents/CAP-05.md) | `direct:owner_readiness`: Actual CAP05 only where selected vertical activates.<br>Source: `task.depends_on[9]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-06](../../parents/CAP-06.md) | `direct:owner_readiness`: Actual CAP06 only where selected; LIF05 remains rights owner.<br>Source: `task.depends_on[10]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-09.freeze_and_readiness](../../cards/LIF-09/freeze_and_readiness.md) | Only for rows in the frozen accepted-source and active/conditional denominator; structural UID coverage is not a semantic witness. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Full producer/persisted chain.
  `task.positive[0]`
- **execute** — Race and remove-property tests.
  `task.adversarial[0]`; `task.removal[0]`
- **execute** — Actual surface/out-of-scope.
  `task.surface`
- **execute** — Persisted proof/fresh reader.
  `task.acceptance_steps[3]`
- **execute** — R17 positive/adversarial/removal.
  `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — Selected controls and removal.
  `solution.implementation_steps[3]`
- **execute** — Actual LIF01-08 artifacts/events and readers.
  `solution.inputs_to_resolve[2]`
- **execute** — task.r19_extension.question_slices[0] crosswalks by actual value to question_ids[0]. Produces an exact-path CAP-04 Q01 witness tied to source/custodian, event/cut, predicate and fresh-reader closure.
  `task.r19_extension.question_slices[0]` (`R18-D22-Q01`); `task.r19_extension.question_ids[0]` (`R18-D22-Q01`)
- **execute** — task.r19_extension.question_slices[1] crosswalks by actual value to question_ids[1]. Produces the distinct Q04 feasibility witness for the selected resource/operation path; Q01/Q05 receipts are not substitutes.
  `task.r19_extension.question_slices[1]` (`R18-D22-Q04`); `task.r19_extension.question_ids[1]` (`R18-D22-Q04`)
- **execute** — task.r19_extension.question_slices[2] crosswalks by actual value to question_ids[2]. Produces the Q05 report/no-report witness for the exact source/event/cut without claiming causality.
  `task.r19_extension.question_slices[2]` (`R18-D22-Q05`); `task.r19_extension.question_ids[2]` (`R18-D22-Q05`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
