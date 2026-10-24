# DEB-06.epoch-reissue-current-decision — Провести epoch reissue до fresh current decision

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [DEB-06](../../parents/DEB-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Verified successor head/reissue produces an append-only, replayable scoped projection that a fresh current-decision consumer accepts.

**Предпочтительное решение.** Reuse integrated epoch-history adapter and CanonicalEpochTransitionVerifier/positive denominator; add the fifth authorized merged-state reissue through LIF-02 canonical currentness/head writer, then UI-19 projection.

**Граница владельца.** One lifecycle vertical: verifier/denominator producer -> reissue artifact -> LIF-02 canonical writer -> UI-19 read. No second head writer; GY-DEF23 appointment stays in DEB-09. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** P0-ACCEPT source; current epoch/claim relation, actual issuer admission only for protected production reissue; its absence stays typed-empty/refused and does not block internal candidate construction or owner-readiness, expected-head and complete merged-state origin; LIF-02 and UI-19 agreed interfaces.; UI-19 actual fresh current-decision acceptance is consumed at canonical composition after LIF-02; it does not gate independent preparation.

**Выход и consumer.** Append-only fifth merge/replay reissue receipt and fresh scoped current-decision projection.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh scientist/validation/decision_validity and UI-19 projection consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Verified successor head/reissue produces an append-only, replayable scoped projection that a fresh current-decision consumer accepts.

**Distinguishing negative.** Merged unrelated bases, stale origin, candidate ID, numerical success alone or hidden programmer error cannot become generic valid/unavailable; historical head remains intact.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Verified successor head/reissue produces an append-only, replayable scoped projection that a fresh current-decision consumer accepts.

**Граница контекста.** Keep one end-to-end owner vertical; verifier and denominator already exist, and GY-DEF23 identity belongs to DEB-09.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-06 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-06 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [UI-19.claim-currentness](../../cards/UI-19/claim-currentness.md) | `acceptance:composition`: Compose the actual fresh UI-19 current-decision projection acceptance after the LIF-02 canonical writer and reissue receipt; this is the canonical acceptance dependency at composition, not a new preparation/start gate. Machine refs: `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/95/acceptance_dependencies/0`; supplier task `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/66`; declared native owner paths `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/66/owner_paths`. The canonical task assigns no concrete output artifact path; bind the actual source/input/backend-bound result during the scoped E02 or FINAL-REVIEW rebind.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.delivery_slices[2]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`
- **execute** — Primary accountability is DEB-06.epoch-reissue-current-decision (execute) for this parent’s source-defined R19 consumer slice: Use existing linked epoch only for material PolicyOS claim reissue. The embedded question_id R18-D04-Q03 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[0]` (`R18-D04-Q03`); `task.r19_extension.question_ids[0]` (`R18-D04-Q03`)
- **execute** — Primary accountability is DEB-06.epoch-reissue-current-decision (execute) for this parent’s source-defined R19 consumer slice: Append linked epoch only when signed PolicyOS claim materially changes. The embedded question_id R18-D04-Q06 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[1]` (`R18-D04-Q06`); `task.r19_extension.question_ids[1]` (`R18-D04-Q06`)
- **execute** — Primary accountability is DEB-06.epoch-reissue-current-decision (execute) for this parent’s source-defined R19 primary writer slice: When the owning claim requires a successor epoch, bind reissue to corrected source, expected head and issuer admission; a correction event alone never triggers automatic re-signing. The embedded question_id R18-D12-Q05 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[2]` (`R18-D12-Q05`); `task.r19_extension.question_ids[2]` (`R18-D12-Q05`)
- **execute** — Primary accountability is DEB-06.epoch-reissue-current-decision (execute) for this parent’s source-defined R19 consumer slice: Append only for material owning-claim change; bind corrected basis, expected prior head and issuer admission. The embedded question_id R18-D14-Q02 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[3]` (`R18-D14-Q02`); `task.r19_extension.question_ids[3]` (`R18-D14-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
