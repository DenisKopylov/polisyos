# CNT-06.causal-support — Связать causal claim с target, estimand и identification

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [CNT-06](../../parents/CNT-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each causal ClaimRecord binds actual evidence, intervention/version, target, comparator, outcome/horizon, estimand, method, assumptions and contrary evidence; support is bounded by identification/transport/selection/interference/overlap.

**Предпочтительное решение.** Reuse Scholar/Scientist study and claim owners. Resolve source-bound evidence and method-specific target support, then bridge typed claim result into selected G2/G3/G4/G5/G6 readers. No paper-count or scenario substitute.

**Граница владельца.** Existing Scientist ClaimRecord/evidence/method owners write under their canonical leases; custodians supply study/protocol/data/local effects; reviewer supplies method assessment/falsifier. Exact path overlaps unresolved after E02.

**Входы.** CNT-01 selected claim/target; CNT-02 resolvable source profile; actual study/data custodian and qualified domain/method reviewer.

**Выход и consumer.** Persisted typed ClaimRecord linking source, target, estimand, method, counterevidence and bounded support/limitation; consumed by Scientist workflow.

**Что можно готовить независимо.** Read-only method/target census may proceed; actual claim use waits on E02 source rebind, selected evidence, reviewer, owner path/lease and permit.

**Где результат соединяется с другими.** Fresh Scientist workflow consumes ClaimRecord, not citation string, and forwards bounded status to actual G2-G6 decision reader.

**Positive.** Exact target/estimand gets supported result or honest partial/nonidentified limit.

**Distinguishing negative.** DAG, fit, consensus, paper count, scenario or mirror is treated as identified/transported independent effect.

**Matched removal.** Remove identification/target validation but keep claim markers: downstream causal reader loses or limits support.

**Граница контекста.** Core causal evidence property remains claim-specific; no universal Bayesian or holdout prerequisite.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Selected claim, target, intervention/population and intended claim type.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Resolvable selected evidence/validation source version; metadata does not prove evidence, labels or permission.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-03.capture-reuse](../../cards/CNT-03/capture-reuse.md) | `acceptance:composition`: CNT-03 persisted capture/admission receipt for selected study/data or permitted validation-label source and exact relevant native method/permission verifier output are composed at CNT-06 acceptance; method assessment and labels retain their native owners.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Removal explicitly targets identification/target validation of causal claims, which the causal-support reader must reject without.
  `task.removal`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `task.surface[0]`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `task.surface[2]`; `task.rollback`; `task.migration`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`; `task.r19_extension.question_slices[5]`; `task.r19_extension.question_slices[6]`; `task.r19_extension.question_slices[7]`; `task.r19_extension.question_slices[8]`; `task.r19_extension.question_slices[9]`; `task.r19_extension.question_slices[10]`; `task.r19_extension.question_slices[11]`; `task.r19_extension.question_slices[12]`; `task.r19_extension.question_slices[13]`; `task.r19_extension.question_slices[14]`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`
- **execute** — These fragments bind actual study/evidence, target/estimand/method, identification/transport/exposure, counterevidence and downstream causal readers; they remain claim-specific.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
