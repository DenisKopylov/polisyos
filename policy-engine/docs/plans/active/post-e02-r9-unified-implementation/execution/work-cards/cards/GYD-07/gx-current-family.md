# GYD-07.gx-current-family — GX по полному current-family output

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-07](../../parents/GYD-07.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Current-family GX passes only after every currently routed red is reconciled at its native owner and GX recomputes the real post-output family.

**Предпочтительное решение.** Reuse WorkspaceLoop, ControlWorker, the current-family GX validator and its recomputed ProductionLoopRunProof; do not repair upstream owners inside GX.

**Граница владельца.** G1/G4/G5/N9-calibration owners resolve their own reds and provide exact-base dispositions. This card owns the GX run/proof and current-family verifier only. Preserve a_spec_gap if the validator permits it; suppressions or a clean failed job never close the family.

**Входы.** The complete current routed-red set and native owner resolutions from G1/G4/G5/N9-calibration.; Actual post-output artifacts and accepted family definition.; Current GX validator and run-proof reader.

**Выход и consumer.** GX current-family result and ProductionLoopRunProof bound to the exact post-output artifact family, including unresolved findings/refusals.

**Что можно готовить независимо.** Reconcile the full current routed-red set at each source owner, replaying inherited reds from the correct slice base under P41.; Run GX only on real post-output artifacts.; Run suppression, wrong-family and clean-failed-job negatives; remove a property while retaining markers.

**Где результат соединяется с другими.** Parent joins upstream owner dispositions with GX’s fresh recomputing result. The inherited “38” is an initial locator, not a current denominator or stop count; owner fixes are not this card’s writes.

**Positive.** The full current family passes from actual artifacts and unsuppressed owner resolutions, with a recomputed run proof.

**Distinguishing negative.** Suppression, wrong family, stale outputs or a clean failed job cannot pass; any unresolved routed owner red remains visible.

**Matched removal.** Remove one required GX property but retain its markers; the validator and fresh consumer must fail.

**Граница контекста.** One verification card, not 38 code fixes. Census the whole current set and name its input denominator (P35); prove property not marker (P29/P33); classify red ownership from the correct base (P41).

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The gx-current-family card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
