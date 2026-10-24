# CNT-03.capture-reuse — Сохранить точное получение и purpose-bound reuse

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [CNT-03](../../parents/CNT-03.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A persisted receipt binds request, producer, exact representation/query receipt, peer, scope, time roles, transforms, rights evidence, verifier and fresh consumer; query-only raw rows stay with custodian.

**Предпочтительное решение.** Reuse existing acquisition planner/executor, epoch admission, Fabric CAS/lineage and security/retention owners. File route persists exact representation; custodian-query route persists only permitted query/result receipt. Recheck rights/currentness per use. WDI single-response rule is route-local; new pagination protocols need separate adapter and recovery proof.

**Граница владельца.** CAP-03 owns acquisition action/producer under its native canonical acquisition lease family; epoch admission/LIF-01/LIF-05 and security/retention retain their canonical admission, deletion and rights semantics. CNT-03 does not duplicate these owners. Exact canonical paths/lease overlap unresolved after E02; assume overlap until resolved.

**Входы.** Sponsor identifies actual custodian; custodian supplies bytes or approved query receipt; rights-holder/institution supplies grant, scope, audience, processor, retention/revocation. WDI is optional, never presumed case-relevant.

**Выход и consumer.** Persisted receipt/CAS object plus lineage and admitted/limited/denied/incomplete result with affected-use links, consumed by fresh admission.

**Что можно готовить независимо.** Read-only protocol census can proceed; protected fetch/store/reuse waits for accepted E02 binding, selected permission, exact lease and permit; no pagination presumed.

**Где результат соединяется с другими.** Receipt → existing fresh epoch/use-admission reader → acquisition consumer/audit. Query route exposes receipt only. Deletion/recovery stays LIF-05/security-owned.

**Positive.** Same artifact reused only for matching purpose/audience after fresh admission; custodian-query never leaks raw rows.

**Distinguishing negative.** More pages, 304 without prior body, foreign tenant, unapproved redirect, forged citation, revoked/narrow grant or purpose change cannot be admitted.

**Matched removal.** Remove terminal receipt or content-bound permission check while retaining cache labels: fresh protected use fails; after deletion, no forbidden bytes return via cache/history/export/restore.

**Граница контекста.** Capture plus fresh use admission is one bridge capability; WDI's page==pages==1 remains unchanged.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Selected case, purpose, audience, actual custodian and allowed-use scope.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:owner_readiness`: Resolvable selected resource/version/representation route; metadata does not establish content or rights.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:owner_readiness`: Existing acquisition action/producer and quotas; reuse, not duplicate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-03`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — These fragments bind exact capture/query receipt to permission, lineage, fresh use, route-local WDI constraints, deletion/recovery and real custodian/rightsholder evidence; mechanism owners remain CAP/LIF/security.
  `task.deliverable`; `task.external_inputs`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface[0]`; `task.surface[1]`; `task.surface[2]`; `task.rollback`; `task.migration`
- **execute** — These fragments bind exact capture/query receipt to permission, lineage, fresh use, route-local WDI constraints, deletion/recovery and real custodian/rightsholder evidence; mechanism owners remain CAP/LIF/security.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`
- **execute** — These fragments bind exact capture/query receipt to permission, lineage, fresh use, route-local WDI constraints, deletion/recovery and real custodian/rightsholder evidence; mechanism owners remain CAP/LIF/security.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
