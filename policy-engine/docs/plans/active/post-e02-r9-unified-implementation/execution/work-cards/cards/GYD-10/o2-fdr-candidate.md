# GYD-10.o2-fdr-candidate — O2 exploratory FDR candidate

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [GYD-10](../../parents/GYD-10.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A real, in-budget DDM signal is recomputed against the accepted FDR plan and complete stream history, then persisted only as candidate_unverified with spend and may_not_use_for.

**Предпочтительное решение.** Reuse OnlineFDRController, DDM events and the canonical HypothesisLedger; extend the existing controller/ledger bridge, never a formulator duplicate ledger.

**Граница владельца.** The existing DDM/FDR owner writes the decision and the existing HypothesisLedger remains the only candidate store. O2 has no world-write or confirmation authority; O1 is a separate route. Source-qualified p/e-value validity and dependence evidence must be resolved rather than self-asserted.

**Входы.** Accepted FDR plan and its method/assumptions.; Real DDM observations and source-qualified detector outputs.; Complete hypothesis-family denominator, look/window, dependence, p/e validity, spend and controller state across restart.

**Выход и consumer.** Persisted attributed candidate receipt with denominator/look/window/spend/rule/source refs and may_not_use_for; fresh ledger reader recomputes its candidate status.

**Что можно готовить независимо.** Rebind actual DDM stream and accepted plan.; Reconcile the denominator, p/e inputs, dependence and state continuity.; Persist only to the canonical ledger and test missing-input refusal and the real candidate-to-review route.

**Где результат соединяется с другими.** Fresh HypothesisLedger readback confirms the candidate and its exact spend/denominator. O1 may later provide independent confirmation; no task DAG edge or direct world write is created by that relation.

**Positive.** One real in-budget anomaly produces a source-attributed candidate with complete persisted stream history and fresh recomputed readback.

**Distinguishing negative.** Invalid or high/repeated q, omitted nulls, policy-induced shift, missing state continuity, unlogged look or direct world write is refused or explicitly limited.

**Matched removal.** Remove the actual look/exposure accounting while retaining FDR labels; the selected known counterexample defeats the guarantee and promotion remains blocked.

**Граница контекста.** R15/R16/R17 and R19 add selection and memory-history constraints to the same exploratory wall, not another controller or ledger. Local p_value <= alpha_spent is not the stream-wide property (P37/P38); preserve candidate-only status.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-10`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The o2-fdr-candidate card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`; `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.product_verification`; `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.product_verification`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
