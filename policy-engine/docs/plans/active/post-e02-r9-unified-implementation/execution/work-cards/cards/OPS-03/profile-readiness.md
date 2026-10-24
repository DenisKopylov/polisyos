# OPS-03.profile-readiness — Показывать readiness по фактически выбранному профилю

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-03](../../parents/OPS-03.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Для выбранной операции readiness становится green только когда все действительно обязательные live dependencies, schema and effective-profile checks are observed; liveness remains process viability.

**Предпочтительное решение.** Extend existing health route, execution-policy resolver and RuntimeServiceContainer projection. Derive requirements from the selected profile composition, not environment strings or backend enums.

**Граница владельца.** Writes the health/readiness projection under OPS-03 `write:exact-path/{canonical_repo_path}`; exact route/container files and overlaps are resolved after E02 rebind. DB/CAS, worker, site, offline and remote owners emit their own health evidence; readiness does not become their verifier or a global admission authority.

**Входы.** Release owner selected profile and required-component contract; OPS-01 effective-profile receipt; DB/schema, CAS, and required OPS-04 worker heartbeat/lease evidence; Selected site/remote/offline owner evidence only for that operation/profile

**Выход и consumer.** Versioned `/ready` and safe operator health payload with effective profile, required live checks and explicit degraded reason; actual admission consumer reads the result.

**Что можно готовить независимо.** Profile composition and health contract can be prepared after interface agreement. Live readiness and admission refusal require the actual selected profile and owner-produced signals; unrelated scope may remain independently eligible.

**Где результат соединяется с другими.** Required runtime components are composed per selected operation. Liveness is not readiness, readiness is not source grant/current claim, and OPS-11 duty deadlines feed LIF-02 claim currentness rather than masquerading as worker heartbeat.

**Positive.** Fresh lease/heartbeat, DB/CAS checks and actual selected profile permit the dependent operation; unrelated independent route remains available only under its own readiness and authority contract.

**Distinguishing negative.** No runner, stale lease, unavailable selected store, weaker profile or failed security posture leaves that selected scope unready without asserting all service liveness failed.

**Matched removal.** Remove live profile/heartbeat/store resolution while leaving status keys; the actual admission consumer still refuses.

**Граница контекста.** One projection property; site/offline/remote checks are inputs, not separate readiness systems. Keep operation-scoped results. P04/P05/P37/P38: readiness is not currentness or source permission and each decisive premise must be sourced and measured.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Readiness changes are rebound to the accepted source/profile and actual consumers.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-01.commissioning](../../cards/OPS-01/commissioning.md) | `direct:owner_readiness`: Consume the effective release profile and digest to determine required services.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for profile-readiness; selectors task.rollback, task.migration, task.rollback_precedence, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.migration_and_rollback, solution.composition_contracts[0], solution.composition_contracts[1], solution.deviation_triggers[0], solution.deviation_triggers[1], solution.inputs_to_resolve[0], solution.inputs_to_resolve[1], solution.input_resolution_rule remain load-bearing.
  `task.rollback`; `task.migration`; `task.rollback_precedence`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`
- **execute** — Direct result/preferred path for profile-readiness; selectors task.deliverable, solution.preferred_solution, solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2], solution.implementation_steps[3] name the work and native owner seam.
  `task.deliverable`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for profile-readiness; selectors task.positive, task.adversarial, task.removal, task.surface, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1] are checked at its actual reader/sink. Bundled subclauses: U022:{"question_id":"R18-D16-Q02","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q02","mechanism_ids":["S16-M2"],"role":"consumer"}; U023:{"question_id":"R18-D17-Q03","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q03","mechanism_ids":["S17-M2","S17-M1"],"role":"primary writer"}; U024:{"question_id":"R18-D17-Q07","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q07","mechanism_ids":["S17-M5","S17-M2","S17-M1"],"role":"consumer"}.
  `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
