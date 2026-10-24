# CNT-05.measure-profile — Версионировать конструкты и конкурирующие меры

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CNT-05](../../parents/CNT-05.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Metric profile binds construct, unit/population/geography/time, instrument, denominator, formula, weights/edge rules and currency/price/accounting basis; alternatives are computed only over comparable qualified inputs.

**Предпочтительное решение.** Reuse existing Foundry/Scientist measurement-definition and calculation owners. Preserve missingness, linkage, subgroup denominator and alternative sensitivity; similar label or value mandate cannot erase incompatible basis.

**Граница владельца.** Existing metric definition/calculation owner writes under its canonical metric lease; dataset custodian supplies definitions/frame/weights/missingness/currency facts. Exact paths and sibling overlap unresolved after E02; do not presume disjoint.

**Входы.** Selected data/source custodian definitions and instruments; method reviewer validates crosswalk. CNT-01 selects relevant class; OECD/WB are references, not case data supplier.

**Выход и consumer.** Versioned measure profile plus alternative/sensitivity/denominator results consumed by claim and mandate-choice readers.

**Что можно готовить независимо.** Read-only definitions and alternative schedule may be prepared; actual computation/admission waits for accepted source, rights, native owner, exact leases and permit.

**Где результат соединяется с другими.** Fresh metric/claim consumer reads formula/version/input adequacy. CNT-05 mandate-choice may select among valid outputs, not repair them.

**Positive.** Different valid bases expose ranking/estimate reversals and subgroup effects.

**Distinguishing negative.** Changed denominator, period, scale, boundary or instrument hides under same metric label; outcome-driven selection appears neutral.

**Matched removal.** Remove formula/version/crosswalk but keep IDs: numerical claim/sensitivity fails or limits.

**Граница контекста.** Owns measurement semantics/results, not normative choice.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Selected case/decision and relevant measure scope.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Selected source identity/version metadata; not dataset definition or authorization.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-03.capture-reuse](../../cards/CNT-03/capture-reuse.md) | `acceptance:composition`: CNT-03 persisted capture/admission receipt for the selected data/instrument source and exact relevant native method/permission verifier output are composed at CNT-05 acceptance; this is not a new start edge or measure-owner appointment.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.deliverable`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.positive`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.surface[0]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.migration`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.product_verification`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.acceptance_discriminators[0]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Bind definition/instrument, aggregation unit, population/denominator and source migration relation. Positive discriminator: Actual exhaustive child aggregates preserve parent total under compatible measure. Adversary: Make children overlap or change denominator while retaining labels; transfer must branch/limit. Removal: Remove mapping evidence but keep ID; fresh consumer returns parent-level.
  `task.r19_extension.question_slices[0]` (`R18-D02-Q01`); `task.r19_extension.question_ids[0]` (`R18-D02-Q01`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Separate target rules from realized membership, denominator and missingness. Positive discriminator: Fixed person target yields 8,100 vs 8,340 links; same target, uncertain denominator. Adversary: Change unit/eligibility with similar count; target forks. Removal: Remove links; target remains, membership unresolved.
  `task.r19_extension.question_slices[1]` (`R18-D02-Q02`); `task.r19_extension.question_ids[1]` (`R18-D02-Q02`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Bind observation period/calendar/frequency separately from effect date. Positive discriminator: Raw events reaggregate to exact windows with original zone version. Adversary: Quarter spans mid-quarter act and only quarterly outcome remains. Removal: Remove raw time basis/rule version; result is conditional.
  `task.r19_extension.question_slices[2]` (`R18-D02-Q03`); `task.r19_extension.question_ids[2]` (`R18-D02-Q03`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Bind aggregation unit, weights, denominator and missingness. Positive discriminator: Source table reproduces aggregate and child margins. Adversary: Use population weights for spatially clustered non-population outcome. Removal: Remove auxiliary support; subgroup transfer vanishes.
  `task.r19_extension.question_slices[3]` (`R18-D02-Q04`); `task.r19_extension.question_ids[3]` (`R18-D02-Q04`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Expose subgroup denominator beside aggregate. Positive discriminator: Newly harmed subgroup changes result. Adversary: Unknown denominator is not zero harm. Removal: Remove subgroup basis: scope narrows. Coverage currently routes this slice selector to CNT-05.mandate-choice/execute; this destination follows its actual question_id and mixed semantics.
  `task.r19_extension.question_slices[5]` (`R18-D05-Q02`); `task.r19_extension.question_ids[5]` (`R18-D05-Q02`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Bind instrument/language version. Positive discriminator: Order effect and direction both visible. Adversary: Changed scale cannot reuse label. Removal: Remove lineage: measure downgrades.
  `task.r19_extension.question_slices[6]` (`R18-D05-Q03`); `task.r19_extension.question_ids[6]` (`R18-D05-Q03`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: For the selected aggregate, resolve the existing measure/target/unit/denominator and aggregation-rule profile, including explicit assumption weights if used. A bound hypothetical weight input is a declared assumption, not an externally endorsed value. Only a normative selected winner additionally requires current principal/rule/version authority; unknown values never default. Positive discriminator: Compatible outcomes and an explicit hypothetical weight profile yield a qualified conditional comparison without collective endorsement; authorized normative selection separately binds its principal. Member outcomes remain available. Adversary: Equal-looking numbers with incompatible measures/denominators cannot aggregate; a hypothetical ranking cannot become a normative winner and unknown weights cannot default. Removal: Remove measure/rule binding: the aggregate loses support even if authority exists. Remove only value authorization: normative winner fails while a supported explicitly hypothetical conditional comparison or vector remains.
  `task.r19_extension.question_slices[8]` (`R18-D20-Q01`); `task.r19_extension.question_ids[8]` (`R18-D20-Q01`)
- **execute** — Measure-profile owns qualified construct, population/denominator, instrument, time and aggregation-rule calculations; it exposes alternatives without authorizing a normative winner. Slice: Qualify target, unit/denominator, temporal/cohort support, selected aggregation-rule profile and explicit hypothetical weights/discounts for every scalar comparison. Hypothetical values are bound assumptions, not endorsement. Add current principal/rule/version authority only for normative selection. Reuse Q01 receipt only when its exact predicate, editions, temporal/cohort scope and rule cover this comparison. Positive discriminator: A qualified temporal measure and explicit discount assumption produce a conditional ranking; an authorized preference additionally selects the normative winner without changing the effect vector. Adversary: Unqualified temporal/cohort aggregation or missing measure basis cannot be laundered by an authorized value rule; hypothetical discount cannot become endorsed social choice. Removal: Remove measure/temporal-rule binding: the scalar comparison loses support. Remove only value authorization: normative selection fails but supported conditional ranking and effect vectors remain.
  `task.r19_extension.question_slices[9]` (`R18-D20-Q06`); `task.r19_extension.question_ids[9]` (`R18-D20-Q06`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[4]` — Produce qualified conditional calculations, value-order alternatives, input/method/rights/currentness bindings and existing result-support status. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[7]` — Preserve denominator alternatives and disclose outcome-driven metric/source selection. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
