# CNT-06.prediction-calibration — Калибровать только объявленный predictive target

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [CNT-06](../../parents/CNT-06.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only a selected prediction claim whose method profile requires calibration gets a versioned calibration relation tied to target, horizon, permitted independent labels and protocol; calibration is not causal identification.

**Предпочтительное решение.** Reuse current quality/calibration owner and independent validation-data route. Bind target/time/label provenance and protocol; do not infer calibration from analogy or invertibility of summaries.

**Граница владельца.** Native calibration owner and validation-data owner retain canonical leases; this card does not create a calibration service or own labels. Exact paths/overlap unresolved after E02; treat sibling writers as potentially shared.

**Входы.** Declared predictive target/method only; independent validation custodian supplies permitted labels and protocol; qualified reviewer validates method.

**Выход и consumer.** Versioned calibration result/limitation with label source, target, horizon and protocol, read by the predictive claim consumer.

**Что можно готовить независимо.** Can declare whether calibration applies; no data collection and no causal blanket gate. Execution waits for target, source permission, E02 rebind and exact lease/permit.

**Где результат соединяется с другими.** Conditionally joins ClaimRecord only where its claim type requires prediction calibration; fresh predictive consumer is named at E02.

**Positive.** Independent authorized labels and adopted protocol validate declared target.

**Distinguishing negative.** Causal evidence, model fit or convenience labels are treated as calibration; no target is named.

**Matched removal.** Remove label/protocol/target validation while retaining status marker: predictive consumer rejects calibration; causal-only claims stay under their own profile.

**Граница контекста.** Separate supplier/property justifies this bounded lane; no universal calibration precondition.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Selected claim, target, intervention/population and intended claim type.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Resolvable selected evidence/validation source version; metadata does not prove evidence, labels or permission.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CNT-03.capture-reuse](../../cards/CNT-03/capture-reuse.md) | `acceptance:composition`: CNT-03 persisted capture/admission receipt for selected study/data or permitted validation-label source and exact relevant native method/permission verifier output are composed at CNT-06 acceptance; method assessment and labels retain their native owners.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This distinct input appoints the validation-label/protocol source role; it is conditional on a declared predictive target and uses the native calibration owner.
  `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
