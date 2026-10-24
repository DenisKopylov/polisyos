# DES-03.frontier-composition — Собрать частичный порядок из фактических результатов

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-03](../../parents/DES-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A fresh Scientist frontier exposes the supported feasible/non-dominated candidates and model/scenario dependence from actual trials and joint simulations while preserving incomparable values, missing completions and bounded coverage.

**Предпочтительное решение.** Consume real trial outputs plus GYD-30 joint simulation and GYD-31 value sets through the existing coordinator. Evaluate only the selected admissible model/scenario set; retain objective tradeoffs and uncertainty axes, never trade hard authority constraints for penalties or invent weights/probabilities.

**Граница владельца.** Consumes trial-binding output and actual GYD-30 CompositionCertificate/GYD-31 ValueOuterSet; those suppliers keep sole artifact writers. DES-03 remains one writer for its native search leases, shared with DES-08 only by exact-path serialized agreement. DES-11 supplies optional actual trajectory results; no dependency edge or new simulator is added.

**Входы.** trial-binding’s bound trials and failures; actual GYD-30 joint results; actual GYD-31 value outer set; LIF-07 influence/revision lineage and selected model/scenario set.; DES-11 trajectory/incumbent outputs only for a case whose declared evaluation requires them; absent suppliers remain conditional/limited, not fabricated.

**Выход и consumer.** Fresh-reader Pareto/model-sensitive frontier with feasibility, per-objective outcomes, unknown/incomparable states, actual cost, revisions and bounded/unrun branches.

**Что можно готовить независимо.** Frontier composition can be prepared against agreed interfaces independently of numerical execution. A claim about joint feasibility, robust dominance or incumbent comparison waits for the selected suppliers and case basis.

**Где результат соединяется с другими.** Join trial-binding’s actual execution with GYD-30 joint outcomes and GYD-31 values in the existing frontier/dossier. The actual consumer is the fresh Scientist frontier; no separate ranking service.

**Positive.** A two-intervention joint effect changes feasibility/ranking against isolated evaluation; conflicting objectives and rival models remain visible, and justified conditional results survive absent collective mandate.

**Distinguishing negative.** A high-score infeasible option, unsupported weight, pointwise interval after adaptive selection, dirty marker without rerun, stale cache, surrogate-only winner, missing model completion or unsupported current-policy dominance cannot appear as a supported winner.

**Matched removal.** Retain scores/frontier labels while removing joint-result, rerun/cache-basis or model-set consumption; the independent small-case oracle and fresh reader detect false dominance or lost support.

**Граница контекста.** This consumer card separates actual numeric work from comparison/composition without inventing a second optimizer. Its bundled predicates are checked against named trial/GYD suppliers; exact UID routing is not itself semantic proof.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-30](../../parents/GYD-30.md) | `direct:interface_agreement`: Consumes the real owner-produced joint CompositionCertificate; no DES-03 certificate copy or writer.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-31](../../parents/GYD-31.md) | `direct:interface_agreement`: Consumes real ValueOuterSet; no invented weights or new value owner.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-07](../../parents/LIF-07.md) | `direct:interface_agreement; conditional_acceptance_requirements:composition`: Consumes actual influence/revision lineage for basis/cache/currentness interpretation; LIF-07 retains invalidation ownership.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; The selected composition claims changed-basis selective execution or cross-run artifact reuse |
| Composition output (не start gate) [DES-03.trial-binding](../../cards/DES-03/trial-binding.md) | Consume only for the exact composition described here: Join trial-binding’s actual execution with GYD-30 joint outcomes and GYD-31 values in the existing frontier/dossier. The actual consumer is the fresh Scientist frontier; no separate ranking service. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — These positive/adversarial/removal/surface clauses are the distinguishing frontier result; bundled trial and joint-simulation subclauses are reconciled against trial-binding and GYD-30/31 outputs.
  `task.positive`; `task.adversarial`; `task.removal`; `task.surface`
- **binding** — Selected objective/value basis is consumed by the frontier; missing external weight/law leaves alternatives set-valued.
  `task.genuine_external_inputs[0]`
- **join** — R15 trajectory/incumbent and selected-profile clauses qualify frontier interpretation; actual DES-11/GYD-30 inputs are conditional and remain their owners.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`; `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.technical_profiles[3]`; `task.r15_extension.product_verification`
- **join** — R16 removal falsifies the rerun/cache-basis/joint consumer bridge at the fresh frontier, not through markers.
  `task.r16_extension.removal`
- **join** — R16 delivery/quality refs are consumer-side composition cases; preserve their exact basis and use actual DES-03/GYD outputs.
  `task.r16_extension.delivery_slices[0]`; `task.r16_extension.delivery_slices[1]`; `task.r16_extension.delivery_slices[2]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`; `task.r16_extension.quality_cases[5]`
- **join** — R17 incumbent-mixture/transition clauses test successor comparison at the frontier using actual trajectory/joint execution; no duplicate optimizer.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`
- **join** — Conditional normative outputs retain unknown collective mandate; frontier reports both admissible conditional schedules without claiming a collective winner. The clause’s named source owner remains the supplier; this route consumes its actual output.
  `task.r19_extension.question_slices[0]`
- **join** — Adaptive-family selection is tested on the real set consumer; pointwise intervals alone cannot prune it. The clause’s named source owner remains the supplier; this route consumes its actual output.
  `task.r19_extension.question_slices[1]`
- **join** — Rival model/scenario alternatives remain partially ordered; no surrogate-only false dominance. The clause’s named source owner remains the supplier; this route consumes its actual output.
  `task.r19_extension.question_slices[4]`
- **join** — Dominant compute equivalence needs actual cost/verifier join and cannot replace social value choice. The clause’s named source owner remains the supplier; this route consumes its actual output.
  `task.r19_extension.question_slices[5]`
- **join** — Optional SCI evidence/weight changes only its supported axis; without owner-backed basis it stays incomparable. The clause’s named source owner remains the supplier; this route consumes its actual output.
  `task.r19_extension.question_slices[6]`
- **join** — Exact edition/denominator aggregation is a frontier input; mismatched period/member cannot support a joint result. The clause’s named source owner remains the supplier; this route consumes its actual output.
  `task.r19_extension.question_slices[7]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[6]`; `task.r19_extension.question_ids[7]`
- **execute** — Implementation step 2 binds the actual joint/model/value consumer; named suppliers retain their own artifact owners.
  `solution.implementation_steps[2]`
- **execute** — Implementation step 3 binds the actual joint/model/value consumer; named suppliers retain their own artifact owners.
  `solution.implementation_steps[3]`
- **execute** — Implementation step 4 binds the actual joint/model/value consumer; named suppliers retain their own artifact owners.
  `solution.implementation_steps[4]`
- **binding** — GYD-30 alone owns CompositionCertificate and GYD-31 owns ValueOuterSet; this card consumes both actual outputs.
  `solution.composition_contracts[0]`
- **join** — Acceptance clauses test actual trial outputs at the fresh Pareto/model-sensitive reader; bundled invalid-trial clauses are reconciled with trial-binding and supplier evidence, not score markers.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Selected simulation/method and value basis is consumed at the frontier; external weights/law are needed only for claims that require them.
  `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
