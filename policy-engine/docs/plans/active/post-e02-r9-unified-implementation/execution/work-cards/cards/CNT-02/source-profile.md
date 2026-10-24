# CNT-02.source-profile — Версионировать описательные профили источников

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [CNT-02](../../parents/CNT-02.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A supported class resolves resource/version/representation/access metadata and a native owner route; a metadata row is discovery, not content-bound admission.

**Предпочтительное решение.** Extend existing catalog/registry with DCAT3 as interchange mapping, keeping native types canonical. Separate issuer/resource/version/coverage/language/jurisdiction/access level from transport/license, authenticity, per-use rights, applicability and freshness.

**Граница владельца.** Existing catalog/source-registry owner writes under its canonical lease family; content owners validate contents and use. Publisher/rightsholder supply facts, not catalog mechanism. Exact paths and overlap with validators unresolved until E02; do not assume disjoint.

**Входы.** CNT-01 selected class/facets when relevant; actual publisher supplies identifiers, versions, representation and updates; rights holder supplies use terms. OECD/WB/HMT/official-law references may be method references, not presumed case suppliers.

**Выход и consumer.** Versioned source-profile record and supported-class→native-validator route consumed by catalog resolver and class-specific admission.

**Что можно готовить независимо.** Prepare read-only metadata crosswalk after accepted source rebind; no body ingestion or rights/applicability/currentness decision by this card. Writes wait for exact owner lease and permit.

**Где результат соединяется с другими.** Existing catalog resolver returns profile; native source-specific validator decides content/use. The profile itself cannot promote status.

**Positive.** A selected supported class resolves exact version/representation and validator; unknown stays unadmitted.

**Distinguishing negative.** Abstract, mirror, alias, stale consolidation or changed edition passes as full/current content.

**Matched removal.** Remove class validator but retain catalog row: fresh admission still rejects unknown class.

**Граница контекста.** Retained: fields share descriptive-profile output; rights and substantive source verification remain with their native owners.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Selected class/scope and common grammar route; a family label does not appoint its publisher as production supplier.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — This fragment set defines the versioned descriptive profile, class-specific owner route, metadata-only limitation, migration and actual publisher/rights-holder inputs; profile owner is not content supplier.
  `task.deliverable`; `task.external_inputs`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface[0]`; `task.surface[1]`; `task.rollback`; `task.migration`
- **execute** — This fragment set defines the versioned descriptive profile, class-specific owner route, metadata-only limitation, migration and actual publisher/rights-holder inputs; profile owner is not content supplier.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
