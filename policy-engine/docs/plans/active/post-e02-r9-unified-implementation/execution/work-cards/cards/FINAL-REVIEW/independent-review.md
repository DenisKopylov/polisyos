# FINAL-REVIEW.independent-review — Провести independent review и delta review

Группа: [G00 — Вход в программу, интеграция и итоговый допуск](../../groups/G00.md). Родитель: [FINAL-REVIEW](../../parents/FINAL-REVIEW.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Independent semantic-scope reviews bind to one immutable freeze candidate; each finding is classified under P40 and blocking repairs are rebounded before replay.

**Предпочтительное решение.** Reuse existing self-review/independent review workflow; assign reviewers by owner scope and keep each review receipt content-bound to the candidate.

**Граница владельца.** Reviewers assess; native owners repair their own paths; root coordinates only. Parent lease family, with exact owner path conflicts unresolved until E02.

**Входы.** FINAL-FREEZE identity, scope-specific source predicates, current owner evidence and independent reviewers.

**Выход и consumer.** Bound review receipts, classified finding ledger, delta-review result and final immutable review identity.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through FINAL-REPLAY dispatcher consumes accepted review identity and complete expected matrix.; composition is limited to this property and the exact original scope.

**Positive.** Each required review scope has an independent qualified decision on the bound candidate; blocking findings are resolved or dispositioned under the competent original criterion, and the exact final replay identity is read back.

**Distinguishing negative.** Self-review, a stale candidate, an unresolved blocking finding, or a post-review change to a load-bearing scope cannot satisfy review; nonblocking observations alone do not force a new expensive replay.

**Matched removal.** Remove a reviewer-to-scope binding or the required delta-review receipt while leaving a green summary; FINAL-REPLAY must not receive a final reviewed identity for that scope.

**Граница контекста.** The review aggregate does not implement product fixes or collapse all scopes into one reviewer/one exit code.

## Первые действия и передача

1. Use the immutable FINAL-FREEZE candidate and complete selected matrix to assign qualified independent reviewers by semantic/evidence scope; bind author, reviewer, candidate identity, and reviewed scope.
2. Review the native owner/output/bridge/fresh-consumer chain and its status, authority, time, and required surface against original predicates; record blockers separately from nonblocking observations and classify findings as new or previously declared class.
3. Batch blocking repairs on the integration branch, obtain independent delta review for changed and newly affected scopes, then read back and bind the final replay tree, inputs, profile, backend, and upstream identities.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [FINAL-FREEZE.immutable-candidate](../../cards/FINAL-FREEZE/immutable-candidate.md) | `direct:frozen_review_candidate`: Consume this supplier’s actual accepted output as required by the canonical FINAL-REVIEW source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `FINAL-REVIEW`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`; `task.r16_extension.quality_cases[5]`; `task.r16_extension.quality_cases[6]`; `task.r16_extension.quality_cases[7]`; `task.r16_extension.quality_cases[8]`; `task.r16_extension.quality_cases[9]`; `task.r16_extension.quality_cases[10]`; `task.r16_extension.quality_cases[11]`; `task.r16_extension.quality_cases[12]`; `task.r16_extension.quality_cases[13]`; `task.r16_extension.quality_cases[14]`; `task.r16_extension.quality_cases[15]`; `task.r16_extension.quality_cases[16]`; `task.r16_extension.product_verification`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.quality_cases[5]`; `task.r17_extension.quality_cases[6]`; `task.r17_extension.quality_cases[7]`; `task.r17_extension.quality_cases[8]`; `task.r17_extension.quality_cases[9]`; `task.r17_extension.quality_cases[10]`; `task.r17_extension.quality_cases[11]`; `task.r17_extension.quality_cases[12]`; `task.r17_extension.quality_cases[13]`; `task.r17_extension.quality_cases[14]`; `task.r17_extension.quality_cases[15]`; `task.r17_extension.quality_cases[16]`; `task.r17_extension.quality_cases[17]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.implementation_steps[5]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`
- **execute** — Primary accountability is FINAL-REVIEW.independent-review (execute) for this parent’s source-defined R19 assurance slice: Test same-use incompatibility and accepted SDD decision; apply active instruction/tool/safety constraints independently. The embedded question_id R18-D23-Q01 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[0]` (`R18-D23-Q01`); `task.r19_extension.question_ids[0]` (`R18-D23-Q01`)
- **execute** — Primary accountability is FINAL-REVIEW.independent-review (execute) for this parent’s source-defined R19 assurance slice: Check the full typed join; preserve normative choice/remainder absent dated authorized decision. The embedded question_id R18-D23-Q03 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[1]` (`R18-D23-Q03`); `task.r19_extension.question_ids[1]` (`R18-D23-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
