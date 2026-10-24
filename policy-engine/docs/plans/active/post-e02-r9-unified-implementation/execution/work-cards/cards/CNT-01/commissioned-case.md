# CNT-01.commissioned-case — Комиссионно выбрать реальный case и владельцев gaps

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CNT-01](../../parents/CNT-01.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Case record связывает решение, claim/gap, facets, цель/audience, sponsor/answerer, owner, next action, consumer и refresh; absent inputs — typed blocker/costed refusal.

**Предпочтительное решение.** Переиспользовать существующие acquisition request/claim references и queue. Runtime integrator binds sponsor-selected scope to existing owner, persisted result and fresh consumer; source card, URL, model suggestion and no-hit remain candidate.

**Граница владельца.** Case-scoped request/evidence stays under the existing acquisition planner/request-queue and claim-registry owners’ native canonical queue/request lease family. Sponsor, institution and custodian supply case/authority/permission; no central registry or approval. E02 must resolve exact paths and overlaps; do not presume disjoint.

**Входы.** Real sponsor selects question, purpose, decision, intervention/estimand, jurisdiction/time/audience and actual answerers; custodian/rightsholder provides or denies route/permission. CNT-04 qualified issuer facts are consumed only for selected successor scope.

**Выход и consumer.** Versioned case/profile request, typed gap disposition, response link and next action read by existing acquisition queue and Expert/Machine audit.

**Что можно готовить независимо.** Conditional facet template and owner census may be prepared; actual commission/protected use waits for accepted E02 source rebind, exact stage pins, leases and permit. Missing external sponsor is a blocker; missing internal producer is assigned work.

**Где результат соединяется с другими.** Join facet-map output to the existing acquisition planner/request queue and audit. A material gap closes only with a native output+fresh consumer or costed refusal that changes dependent status; no new authority is issued.

**Positive.** Every selected gap has named route/owner/consumer or costed refusal; irrelevant families stay out of selected case.

**Distinguishing negative.** URL/card/family label/no-hit/LLM suggestion is offered as evidence or authority; no real commission is selected.

**Matched removal.** Keep queue labels but remove reconciliation: a fresh reader cannot assert real owner, permitted route or consumer.

**Граница контекста.** Binds case identity, purpose and owner route; consumes qualified CNT-04 issuer/delegation facts only if a selected successor/contest requires them.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CNT-01.facet-map](../../cards/CNT-01/facet-map.md) | Only for the selected same-scope composition described by this card: Join facet-map output to the existing acquisition planner/request queue and audit. A material gap closes only with a native output+fresh consumer or costed refusal that changes dependent status; no new authority is issued. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `task.deliverable`; `task.external_inputs`
- **binding** — The selected-case positive/removal cases ask whether real gap owner/route/consumer exists; queue labels alone are insufficient.
  `task.positive`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `task.adversarial`
- **binding** — The selected-case positive/removal cases ask whether real gap owner/route/consumer exists; queue labels alone are insufficient.
  `task.removal`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `task.surface[0]`; `task.surface[1]`; `task.rollback`; `task.migration`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `task.selection_output`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `solution.preferred_solution`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`
- **binding** — The selected-case positive/removal cases ask whether real gap owner/route/consumer exists; queue labels alone are insufficient.
  `solution.acceptance_discriminators[2]`
- **execute** — These fragments specify the real sponsor-selected case, scoped request, gap route, audit, next action, refusal, migration and external inputs; commissioning consumes owner routes but does not create source/authority.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
