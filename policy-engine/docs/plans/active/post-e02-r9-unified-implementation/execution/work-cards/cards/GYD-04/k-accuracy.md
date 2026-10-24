# GYD-04.k-accuracy — Повно-деномінаторна точність correspondence

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-04](../../parents/GYD-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Candidate correspondence precision and recall are available only from independent adjudication over the complete source-pinned denominator.

**Предпочтительное решение.** Reuse Scholar provider attempts, models and enrichment path; add the source-pinned label/denominator binding to the existing accuracy instrument.

**Граница владельца.** Scholar retrieval failover and AxisEntailmentWitness are candidate inputs/controls, never semantic deciders. The K adjudicator and competent labels are separately appointed evidence; do not self-appoint or treat model output as ground truth.

**Входы.** Complete versioned correspondence denominator and label rule.; Competently appointed adjudicator with declared independence scope.; Source snapshot, candidate output, conflict/exclusion and provenance records.

**Выход и consumer.** Persisted candidate accuracy receipt with exact denominator, labels, provenance, version and exclusions; fresh consumer reports metrics or unavailable.

**Что можно готовить независимо.** Pin the full denominator and adjudication rule.; Resolve the adjudicator and claim the narrow independence property actually supported.; Bind labels to the source snapshot and compute precision/recall at the actual correspondence consumer.

**Где результат соединяется с другими.** The fresh accuracy consumer joins candidate output, independent labels, full denominator and adjudicator identity; missing inputs keep accuracy unavailable.

**Positive.** The adjudicated positive/negative set resolves full-denominator accuracy at the consumer.

**Distinguishing negative.** Self-score, present-null, partial denominator or AxisEntailmentWitness alone cannot decide accuracy.

**Matched removal.** Remove adjudicator or denominator binding; the receipt reports unavailable and does not silently retain a prior value.

**Граница контекста.** One measured property; retrieval attempts and witnesses are not new accuracy owners. Apply K14 only to the explicit independent-correctness claim (P14); keep source labels and their authority distinct.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — The k-accuracy card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`
- **execute** — Both canonical slice occurrences are identical by parent/question_id value. The assurance slice requires full-denominator, material-stratum error measurement with independent adjudication; this card owns the persisted accuracy receipt and refuses model-scored or partial-denominator metrics.
  `task.r19_extension.question_slices[0]` (`R18-D02-Q02`); `task.r19_extension.question_ids[0]` (`R18-D02-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
