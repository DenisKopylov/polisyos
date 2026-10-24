# GYD-11.as3-o3-mutations — AS3: пять мутаций на реальном O3 consumer

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-11](../../parents/GYD-11.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The actual O3 world consumer refuses each of the five isolated mutation cases and accepts adjacent valid controls against the exact immutable 24-packet corpus.

**Предпочтительное решение.** Use one appointed Runtime/quality sealed packet/oracle owner and the existing world_model_record/Fabric consumer; run the real consumer and persist its receipts.

**Граница владельца.** The existing WMR/Fabric owner remains the sole world writer. This card verifies O3 behavior; it cannot activate O1, change structural-write rules, or create a second test writer. Retain quarantine and mutation history through reprocessing.

**Входы.** Accepted GY-AS3 packet identities and sealed oracle.; Five isolated mutations plus adjacent valid controls.; Actual O3/WMR/Fabric consumer artifacts; applicable O1 or structural rule only for the relevant positive.

**Выход и consumer.** Versioned AS3 corpus and persisted success/refusal receipt for every mutation/control from the production O3 consumer.

**Что можно готовить независимо.** Freeze the exact original 24 packets, 5 mutation definitions and valid controls at source rebind.; Run each through the production O3 boundary, recomputing from bytes and refs.; Change observation process for self-confirmation, attempt full reprocessing, and retain quarantine reason.

**Где результат соединяется с другими.** The corpus join is the actual O3 consumer plus persisted receipt readback. Effect-posterior positives require GYD-09/WP-01; structural cases use their distinct actual write rule. Corpus research itself is non-authoritative.

**Positive.** Each of the five source-defined mutations independently fails at the real O3 consumer and adjacent valid controls pass under the applicable admission rule.

**Distinguishing negative.** Candidate-only evidence, O1/context mismatch, self-confirmation after reprocessing, replay or quarantine release stays red; missing mutation identities remain not_established.

**Matched removal.** Remove one actual consumer mutation while keeping its corpus seal and markers; the behavioral corpus check fails.

**Граница контекста.** One verification battery, not a diagnosis holdout or tuning path. Prove the source mutation set and run the writer itself (P29/P33/P37/P38); preserve GYD-09 activation boundary and separate structural rule.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-11`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The as3-o3-mutations card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
