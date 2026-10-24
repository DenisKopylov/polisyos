# UI-19.claim-currentness — Показать DS18 transition после replayable lineage

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [UI-19](../../parents/UI-19.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Selected claim/decision currentness requires complete DS18 denominator, CAP-04 events, LIF-02 reaction, DEB-06 lineage, DEB-14 ruling, configured GY-CR4 reader and replayable transition; original as-known epoch remains.

**Предпочтительное решение.** Reuse epoch_validity_cascade and decision_validity; consume CAP-04/LIF-02/DEB-06/DEB-14 owner outputs, no second engine.

**Граница владельца.** UI-19 owns selected fresh projection only; CAP-04, LIF-02, DEB-06, DEB-14 and GY-CR4 stay native; code cannot appoint signers.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Original DS18 denominator/claim, CAP-04 source events, LIF-02 reaction, DEB-06 lineage, DEB-14 ruling and real GY-CR4 reader.

**Выход и consumer.** Fresh API/MACHINE/audit returns current/limited/pending with source cut, predecessors, expected head, times and as-known issue.

**Что можно готовить независимо.** Bind full selected denominator/readers; prep on interfaces; missing producer/reader keeps positive unavailable.

**Где результат соединяется с другими.** Compose all source/lifecycle/ruling/lineage outputs via existing cascade; no task-level cycles or UI-17 substitution. The fresh projection includes LIF-02’s conditional selected-duty consequence when a standing-duty guarantee applies; OPS-11 accepted-duty evidence joins inside LIF-02 at composition, with no UI→OPS-11 gate. For a selected restored protected scope, the reader composes LIF-02 material replay/currentness, LIF-05 per-placement rights/retention, and the existing OPS-05 restore-cut receipt; OPS-05 owns restore enablement, so the projection adds no independent admission bit.

**Positive.** Only replayable reconciled transition/current epoch and scoped lineage render current.

**Distinguishing negative.** Legacy branch, opt-in None, hash equality, caller label, missing event, blanket invalidation or unappointed signer remain unknown/refused.

**Matched removal.** Remove reader/lineage with green marker: fresh consumer cannot assert currentness.

**Граница контекста.** One validity-cascade projection; original DS18 denominator and new R9 event classes remain separately reconciled.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Enrolled source/right reaction and current-decision/fence output through existing cascade.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-04](../../parents/CAP-04.md) | `acceptance:composition`: Source-specific change event and scoped cut/head/time consumed by DS18 currentness.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [DEB-14.scope-ruling-currentness](../../cards/DEB-14/scope-ruling-currentness.md) | `acceptance:composition`: Purpose-scoped four-way ruling evidence for selected lifecycle admission/replay.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [DEB-06.epoch-reissue-current-decision](../../cards/DEB-06/epoch-reissue-current-decision.md) | `acceptance:composition`: Persisted current-decision lineage/reissue receipt, predecessors, expected head and as-known issue.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-19`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — This source field contributes to claim-currentness's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.preferred_solution, task.deliverable.
  `task.deliverable`; `solution.preferred_solution`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2], task.adversarial, task.positive, task.removal.
  `task.positive`; `task.adversarial`; `task.removal`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **binding** — Enumerated surfaces are readers of one canonical card result, not separate transport owners. Source selectors: task.surface[0], task.surface[1], task.surface[2].
  `task.surface[0]`; `task.surface[1]`; `task.surface[2]`
- **binding** — Preserves history/rollback/lifecycle semantics consumed by the existing owner. Source selectors: solution.migration_and_rollback, task.migration, task.rollback.
  `task.rollback`; `task.migration`; `solution.migration_and_rollback`
- **join** — Binds source/oracle/owner behavior or fresh consumer required by the card; parent stage remains canonical. Source selectors: task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4].
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`
- **binding** — This source field contributes to claim-currentness's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0], solution.deviation_triggers[1], solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4].
  `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`
- **binding** — Routes extension by its property into the existing currentness/rights/time/audience/evidence owner. Source selectors: task.r17_extension.adversarial, task.r17_extension.delivery_slices[0], task.r17_extension.positive, task.r17_extension.product_verification, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r17_extension.quality_cases[4], task.r17_extension.quality_cases[5], task.r17_extension.removal, task.r17_extension.requirement, task.r19_extension.acceptance_ref, task.r19_extension.composition_contract_ref, task.r19_extension.product_verification, task.r19_extension.status, task.r19_extension.writer_rule.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.quality_cases[5]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **binding** — Q03 appends correction/reply to exact parent and separates informal evidence, formal act and PolicyOS reaction. Source selectors: task.r19_extension.question_ids[3], task.r19_extension.question_slices[0].
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_ids[3]`
- **binding** — R18-D14-Q02 is routed to the card consuming its named owner output and preserving status/authority/time. Source selectors: task.r19_extension.question_ids[0], task.r19_extension.question_slices[1].
  `task.r19_extension.question_slices[1]`; `task.r19_extension.question_ids[0]`
- **binding** — Q05 appends attributed response/supersession without adjudicating or overwriting the original. Source selectors: task.r19_extension.question_ids[1], task.r19_extension.question_slices[2].
  `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[1]`
- **binding** — R18-D20-Q05 is routed to the card consuming its named owner output and preserving status/authority/time. Source selectors: task.r19_extension.question_ids[2], task.r19_extension.question_slices[3].
  `task.r19_extension.question_slices[3]`; `task.r19_extension.question_ids[2]`
- **execute** — Advances the same native owner result; exact path/lease resolves at P0. Source selectors: solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3].
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2], solution.composition_contracts[3].
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.input_resolution_rule, solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.inputs_to_resolve[2].
  `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
