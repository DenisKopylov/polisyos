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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CNT-01.facet-map](../../cards/CNT-01/facet-map.md) | Only for the selected same-scope composition described by this card: Join facet-map output to the existing acquisition planner/request queue and audit. A material gap closes only with a native output+fresh consumer or costed refusal that changes dependent status; no new authority is issued. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

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
- **execute** — Commissioned-case owns the sponsor-selected case, exact scope, custody references, answerer and successor-selection result; the facet map is the shared grammar, not a case authority. Slice: Bind candidate ref to actual sponsor, decision, scope, purpose, audience and accountable principal; preserve typed blocker when absent. Positive discriminator: Real commission is linked to origin and owner/consumer route. Adversary: Search no-hit, LLM summary, alarm or participant signature alone cannot commission. Removal: Remove authority relation: candidate remains useful but protected case use cannot pass.
  `task.r19_extension.question_slices[0]` (`R18-D01-Q01`); `task.r19_extension.question_ids[0]` (`R18-D01-Q01`)
- **execute** — Commissioned-case owns the sponsor-selected case, exact scope, custody references, answerer and successor-selection result; the facet map is the shared grammar, not a case authority. Slice: Resolve the exact contest scope and sponsor selection against the current commission and authenticated effective delegation; consume CNT-04-qualified issuer/effectivity facts and seek new authority only for uncovered scope. Positive discriminator: CNT-04 verifies the instrument; its delegation covers the exact successor scope, which the sponsor selects append-only without a new institution act. Adversary: Keep the declaration but resolve delegation expiry or scope so the child is uncovered; limit only that child. Removal: Remove commission/delegation scope resolution while keeping frame and labels; protected successor authority is not established.
  `task.r19_extension.question_slices[1]` (`R18-D01-Q02`); `task.r19_extension.question_ids[1]` (`R18-D01-Q02`)
- **execute** — Commissioned-case owns the sponsor-selected case, exact scope, custody references, answerer and successor-selection result; the facet map is the shared grammar, not a case authority. Slice: Distinguish case_id from a stable adapter-namespace-qualified PolicyOS-local custody ref; accept optional external time-qualified aliases, with no global owner/issuer/schema/cardinality decision. Positive discriminator: No external ID: a local ref is explicitly reused across two distinct case histories; a later verified alias appends without rewriting either. Adversary: A reused/rotated token or same value in an unqualified namespace does not merge cases. Removal: Removing namespace or alias verification limits that cross-reference; local ref and separate histories remain.
  `task.r19_extension.question_slices[2]` (`R18-D01-Q03`); `task.r19_extension.question_ids[2]` (`R18-D01-Q03`)
- **execute** — Commissioned-case owns the sponsor-selected case, exact scope, custody references, answerer and successor-selection result; the facet map is the shared grammar, not a case authority. Slice: Resolve current commission and successor selection against sponsor, act and exact child scope, consuming CNT-04-qualified issuer/effectivity facts; accept covered effective delegation and seek new authority only for uncovered scope. Positive discriminator: CNT-04 verifies effective delegation; CNT-01 confirms it covers the split, then records sponsor selection, distinct child IDs and parent links without a new instrument. Adversary: Keep delegation bytes but resolve expiry/coverage outside one child; only that child authority stays limited. Removal: Remove commission/delegation scope resolution while retaining child IDs; fresh protected reader cannot establish authority and candidate work remains.
  `task.r19_extension.question_slices[3]` (`R18-D01-Q04`); `task.r19_extension.question_ids[3]` (`R18-D01-Q04`)
- **execute** — Commissioned-case owns the sponsor-selected case, exact scope, custody references, answerer and successor-selection result; the facet map is the shared grammar, not a case authority. Slice: Комиссионно выбрать реальный matter/source/answerer и allowed use. Positive discriminator: До protected use bound реальная запись и competent answerer. Adversary: URL или generic card выдается за commissioned act. Removal: Убрать source/scope relation при labels: consumer не подтверждает act.
  `task.r19_extension.question_slices[4]` (`R18-D22-Q01`); `task.r19_extension.question_ids[4]` (`R18-D22-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
