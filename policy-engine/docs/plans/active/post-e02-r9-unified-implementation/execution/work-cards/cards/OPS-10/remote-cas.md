# OPS-10.remote-cas — Квалифицировать выбранный remote CAS adapter

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-10](../../parents/OPS-10.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For one exact selected provider/config, an owner-scoped immutable object/version is the one actually read/written, caches are cell-isolated, and ambiguous multi-store outcomes require reconciliation.

**Предпочтительное решение.** Extend existing S3/GCS/caching adapter owners with per-provider conditional writes, namespace/owner resolution, bounded reads, lifecycle and exact restore conformance. DB pointer/object writes remain a recoverable sequence; a hash is integrity, not authority.

**Граница владельца.** Writes use the native backend owner under `write:backend-adapter/{backend}` and exact resource key `resource:cas/{tenant}/{cell}/{root}`. Resolve provider-specific file/API paths and cell lease overlap after E02; same labels do not prove disjointness.

**Входы.** Selected provider/account, exact bucket/prefix/IAM/config and conditional-write route; OPS-06 owner/grant authorization for actual object access; OPS-05 directional reader/restore join; OPS-03 selected readiness; OPS-08 measured capacity and bounded byte/request limits

**Выход и consumer.** Adapter conformance receipt plus version/owner-bound read/write outcome, consumed by fresh authorized CAS reader and OPS-05 restore owner.

**Что можно готовить независимо.** Local profile remains default. An exact remote config can prepare independently; activation follows named custody/topology/operability/availability/scale/cost objective and exact provider operation semantics. A new bucket name is not a new adapter.

**Где результат соединяется с другими.** Selected adapter and exact provider API behavior compose with OPS-05 recovery, OPS-06 permission and OPS-03 readiness; adapter conformance does not imply multi-cell activation, provider-wide parity or complete recovery.

**Positive.** Concurrent owner-scoped create/read, multipart/version/lifecycle behavior and quarantine restore agree on manifest/hash/reference and a fresh authorized reader.

**Distinguishing negative.** Cross-cell id/cache collision, partial multipart write, stale version, credential loss, outage or old-manifest rollback cannot disclose or silently lose/authorize an object.

**Matched removal.** Remove scoped-owner/read/restore checks but keep enum/config; cross-cell and stale-version consumer probes fail.

**Граница контекста.** Provider-specific conformance is one selected storage capability. Same-API config changes to atomicity, retention, key or topology need their own exact test. G09 is storage/recovery home; P27/P32/P38 require true actual operation test.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted-source rebind and selected-tier stage remain parent rules; do not require cloud profile for local scopes.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-03.profile-readiness](../../cards/OPS-03/profile-readiness.md) | `direct:owner_readiness`: Consume actual selected backend/cell readiness only for activated operation.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-05](../../parents/OPS-05.md) | `direct:owner_readiness`: Join actual backend read/version and restore result for the selected remote storage path.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Resolve owner/action permission at the actual object reader; a bucket key or hash does not authorize.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-08](../../parents/OPS-08.md) | `direct:owner_readiness`: Use measured remote request and host/replica capacity for the selected class only.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-10`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for remote-cas; selectors task.rollback, task.migration, task.r17_extension.delivery_slices[0], task.r17_extension.delivery_slices[1], task.r17_extension.product_verification, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], task.r19_extension.question_ids[3], task.r19_extension.writer_rule, solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.migration_and_rollback, solution.composition_contracts[0], solution.composition_contracts[1], solution.composition_contracts[2], solution.deviation_triggers[1], solution.inputs_to_resolve[0] remain load-bearing.
  `task.rollback`; `task.migration`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.product_verification`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.writer_rule`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`
- **execute** — Direct result/preferred path for remote-cas; selectors task.r17_extension.requirement, solution.preferred_solution, solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3] name the work and native owner seam.
  `task.r17_extension.requirement`; `solution.preferred_solution`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for remote-cas; selectors task.positive, task.adversarial, task.removal, task.surface, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.r17_extension.positive, task.r17_extension.adversarial, task.r17_extension.removal, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r17_extension.quality_cases[3], task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2], task.r19_extension.question_slices[3], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1], solution.acceptance_discriminators[2] are checked at its actual reader/sink. Bundled subclauses: U034:{"question_id":"R18-D18-Q04","solution_ref":"solutions/lifecycle-r19/S15.md#r18-d18-q04","mechanism_ids":["S15-M2","S15-M3"],"role":"consumer"}; U035:{"question_id":"R18-D17-Q01","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q01","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"assurance"}; U036:{"question_id":"R18-D19-Q04","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q04","mechanism_ids":["S19-M1","S19-M2"],"role":"input collection"}; U037:{"question_id":"R18-D19-Q05","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q05","mechanism_ids":["S19-M1","S19-M3"],"role":"input collection"}.
  `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
