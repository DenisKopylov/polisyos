# CNT-07.testimony — Сохранить testimony, occurrence, context и permission

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CNT-07](../../parents/CNT-07.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Permissioned account/occurrence binds source, context, elicitation/translation, audience/use, correction/challenge and affected claim; proves only what source permits, not unique identity or prevalence.

**Предпочтительное решение.** Reuse existing claim, permission and lineage owners; keep raw/private material at custodian when possible. Preserve dissent, absence, translation and revocation without rewriting history.

**Граница владельца.** Speakers/holders or authorized body supply accounts/grants; current evidence/permission/lineage owners record them under canonical leases. No inferred identity/representation. Exact path and lease overlap unresolved after E02.

**Входы.** Real commissioned audience, actual speaker/holder, process custodian, consent, context, translation and correction route; no source card appoints them.

**Выход и consumer.** Scoped account/occurrence/translation evidence with affected-use and rights links; read by claim evidence and permitted reviewer/Atlas surfaces.

**Что можно готовить независимо.** Field map/read-only planning may proceed; protected collection/use awaits actual commission, permission, E02 rebind, exact lease and community protocol if applicable.

**Где результат соединяется с другими.** Fresh claim reader admits only scoped permitted assertion; audience surfaces obey grant and retain limits.

**Positive.** Permitted contextual testimony informs only linked claim with dissent/selection limits visible.

**Distinguishing negative.** Occurrence becomes person, report becomes prevalence, translation becomes original wording, or reviewer sample becomes frontline evidence.

**Matched removal.** Remove context/permission/affected-use link while retaining checksum: fresh protected use fails or limits; only linked uses stale.

**Граница контекста.** Account/permission is distinct from process representation, normative mandate and capacity.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Case scope, selected audience/remit, actual answerer roles and relevant claims.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Selected source identity/version route where relevant; metadata is not consent, mandate or capacity.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-03.capture-reuse](../../cards/CNT-03/capture-reuse.md) | `acceptance:composition`: CNT-03 persisted capture/admission receipt for a selected account and exact relevant native permission/method verifier output are composed at CNT-07 acceptance; it does not appoint a speaker, authority or evidence owner.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These clauses concern permitted account/occurrence/context/translation, audience, correction, challenge, revocation and community protocols; actual speakers/holders or community authority supply content.
  `task.surface[0]`
- **execute** — These clauses concern permitted account/occurrence/context/translation, audience, correction, challenge, revocation and community protocols; actual speakers/holders or community authority supply content.
  `task.surface[2]`
- **execute** — These clauses concern permitted account/occurrence/context/translation, audience, correction, challenge, revocation and community protocols; actual speakers/holders or community authority supply content.
  `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`
- **execute** — These clauses concern permitted account/occurrence/context/translation, audience, correction, challenge, revocation and community protocols; actual speakers/holders or community authority supply content.
  `solution.acceptance_discriminators[1]`
- **execute** — These clauses concern permitted account/occurrence/context/translation, audience, correction, challenge, revocation and community protocols; actual speakers/holders or community authority supply content.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`
- **execute** — Testimony owns permissioned, contextualized account/occurrence evidence and its affected-use limits; it cannot supply mandate, representation authority or causal proof. Slice: Preserve testimony/contest context, selection/representation, translation, permission, audience, dissent and correction; do not infer mandate or scope authority. Positive discriminator: Permitted, contextualized testimony informs only the affected claim with representation limits visible. Adversary: Unpermitted input or self-appointed speaker cannot authorize a new frame or broaden scope. Removal: Keep report label but remove context/permission resolution; fresh protected use cannot rely on testimony.
  `task.r19_extension.question_slices[0]` (`R18-D01-Q02`); `task.r19_extension.question_ids[0]` (`R18-D01-Q02`)
- **execute** — Testimony owns permissioned, contextualized account/occurrence evidence and its affected-use limits; it cannot supply mandate, representation authority or causal proof. Slice: Resolve whether testimony/participation context, selection, translation and permission cover each child use; preserve dissent and limits, not authority to commission. Positive discriminator: Existing permission covers testimony for child A but not B; only A may reuse it as a basis. Adversary: Unpermitted, misrepresented or out-of-context testimony cannot support the changed child scope. Removal: Keep participant/citation labels but remove child-specific context/permission; the child cannot rely on that testimony.
  `task.r19_extension.question_slices[1]` (`R18-D01-Q04`); `task.r19_extension.question_ids[1]` (`R18-D01-Q04`)
- **execute** — Testimony owns permissioned, contextualized account/occurrence evidence and its affected-use limits; it cannot supply mandate, representation authority or causal proof. Slice: Bind views to exact process context. Positive discriminator: Post-evidence change remains process-specific. Adversary: Hidden order/attrition defeats prevalence. Removal: Remove process refs: context-only.
  `task.r19_extension.question_slices[6]` (`R18-D05-Q03`); `task.r19_extension.question_ids[6]` (`R18-D05-Q03`)
- **execute** — Testimony owns permissioned, contextualized account/occurrence evidence and its affected-use limits; it cannot supply mandate, representation authority or causal proof. Slice: Use permissioned account path; separate report, consent, verification and cause interpretation. Positive discriminator: Permitted account reaches claim with uncertainty and correction path. Adversary: One report equals person count, prevalence or verified event. Removal: Remove permission/use binding but retain checksum: limit claim and protect private data.
  `task.r19_extension.question_slices[12]` (`R18-D22-Q05`); `task.r19_extension.question_ids[14]` (`R18-D22-Q05`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[2]` — Supply contextual testimony and participant selection/representation limits separately from appointed authority. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[4]` — Keep preferences/testimony distinct from an authorized mandate. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[5]` — Bind new affected-group evidence, source, pathway and representation limits. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[8]` — Resolve individual consent, source context and permitted quotation separately. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[10]` — Preserve dissent/correction and audience permission as testimony, not institutional decision. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[13]` — Retain actual participant account/permission separately from representation and mandate. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[14]` — Testimony is not measured capacity. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
