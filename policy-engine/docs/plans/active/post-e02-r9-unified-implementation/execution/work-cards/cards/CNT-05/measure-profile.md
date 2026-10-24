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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Selected case/decision and relevant measure scope.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Selected source identity/version metadata; not dataset definition or authorization.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-03.capture-reuse](../../cards/CNT-03/capture-reuse.md) | `acceptance:composition`: CNT-03 persisted capture/admission receipt for the selected data/instrument source and exact relevant native method/permission verifier output are composed at CNT-05 acceptance; this is not a new start edge or measure-owner appointment.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-05`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

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
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_slices[3]`; `task.r19_extension.question_slices[4]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.r19_extension.question_slices[6]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `task.r19_extension.question_slices[8]`; `task.r19_extension.question_slices[9]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.acceptance_discriminators[0]`
- **execute** — These clauses define/version/compute measurement basis, denominator/instrument/weights/crosswalk, sensitivity and comparison; data owner supplies definitions, metric mechanism owner computes.
  `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
