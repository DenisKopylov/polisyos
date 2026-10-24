# FINAL-REVIEW.independent-review — Провести independent review и delta review

Группа: [G00 — Вход в программу, интеграция и итоговый допуск](../../groups/G00.md). Родитель: [FINAL-REVIEW](../../parents/FINAL-REVIEW.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Independent semantic-scope reviews bind to one immutable freeze candidate; each finding is classified under P40 and blocking repairs are rebounded before replay.

**Предпочтительное решение.** Reuse existing self-review/independent review workflow; assign reviewers by owner scope and keep each review receipt content-bound to the candidate.

**Граница владельца.** Reviewers assess; native owners repair their own paths; root coordinates only. Parent lease family, with exact owner path conflicts unresolved until E02.

**Входы.** FINAL-FREEZE identity, scope-specific source predicates, current owner evidence and independent reviewers.

**Выход и consumer.** Bound review receipts, classified finding ledger, delta-review result and final immutable review identity.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through FINAL-REPLAY dispatcher consumes accepted review identity and complete expected matrix.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Independent semantic-scope reviews bind to one immutable freeze candidate; each finding is classified under P40 and blocking repairs are rebounded before replay.

**Distinguishing negative.** Review against a moving candidate, reviewer self-attestation as independence, unclassified repeat class or omitted blocking delta cannot pass.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Independent semantic-scope reviews bind to one immutable freeze candidate; each finding is classified under P40 and blocking repairs are rebounded before replay.

**Граница контекста.** The review aggregate does not implement product fixes or collapse all scopes into one reviewer/one exit code.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [FINAL-FREEZE.immutable-candidate](../../cards/FINAL-FREEZE/immutable-candidate.md) | `direct:frozen_review_candidate`: Consume this supplier’s actual accepted output as required by the canonical FINAL-REVIEW source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `FINAL-REVIEW`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`; `task.r16_extension.quality_cases[5]`; `task.r16_extension.quality_cases[6]`; `task.r16_extension.quality_cases[7]`; `task.r16_extension.quality_cases[8]`; `task.r16_extension.quality_cases[9]`; `task.r16_extension.quality_cases[10]`; `task.r16_extension.quality_cases[11]`; `task.r16_extension.quality_cases[12]`; `task.r16_extension.quality_cases[13]`; `task.r16_extension.quality_cases[14]`; `task.r16_extension.quality_cases[15]`; `task.r16_extension.quality_cases[16]`; `task.r16_extension.product_verification`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.quality_cases[5]`; `task.r17_extension.quality_cases[6]`; `task.r17_extension.quality_cases[7]`; `task.r17_extension.quality_cases[8]`; `task.r17_extension.quality_cases[9]`; `task.r17_extension.quality_cases[10]`; `task.r17_extension.quality_cases[11]`; `task.r17_extension.quality_cases[12]`; `task.r17_extension.quality_cases[13]`; `task.r17_extension.quality_cases[14]`; `task.r17_extension.quality_cases[15]`; `task.r17_extension.quality_cases[16]`; `task.r17_extension.quality_cases[17]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.implementation_steps[5]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
