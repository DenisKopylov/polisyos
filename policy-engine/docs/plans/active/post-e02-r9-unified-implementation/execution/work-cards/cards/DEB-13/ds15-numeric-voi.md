# DEB-13.ds15-numeric-voi — Провести DS15 numeric-VOI до fresh consumer

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DEB-13](../../parents/DEB-13.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A versioned source-bound numeric-VOI result reaches a fresh DS15/UI-17 consumer under explicit refusal when its supported basis is absent; gross EVSI is independent of cost.

**Предпочтительное решение.** Reuse acquisition_planner.py SearchLedger/refusal and native UI-17; appoint metric owner/oracle, persist versioned result, and keep CAP-03 as sole cost writer.

**Граница владельца.** Metric producer owns VOI formula/artifact; CAP-03 alone writes cost. DEB-13 reads CAP-03 cost only for net/ENBS or cost-sensitive selected routes. Native exact-path lease family; exact paths unresolved until E02. Atlas/DS15 scope owner под координацией P0/root commissions native metric/decision owner; при отсутствии producer DEB-13 исследует и предлагает extension этого owner, затем реализует после actual owner decision. UI-17 остаётся consumer, не вторым metric writer.

**Входы.** Owner decision and estimand/oracle; versioned source inputs and actual fresh DS15/UI-17 route; conditional CAP-03 persisted cost for net/ENBS/cost-sensitive use only.; UI-17 actual route acceptance is composed with the persisted supported metric/refusal; cost-sensitive conditions remain as specified and do not gate preparation.

**Выход и consumer.** Versioned gross EVSI or cost-bound net/ENBS artifact with provenance/refusal, consumed by fresh route/UI projection.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh DS15/UI-17 selected-route consumer; CAP-03 receipt is consumed only when the selected metric requires cost.; composition is limited to this property and the exact original scope.

**Positive.** Для выбранных finite alternatives/state/observation law exact finite-sum gross EVSI совпадает с независимым oracle в declared tolerance; zero-information/irrelevant-observation case даёт ноль в этой tolerance. Смена bound utility/likelihood меняет результат когда это следует из oracle. Explicit hypothetical/unqualified, но полностью заданные inputs дают labeled conditional gross estimate, не policy value. Для qualified policy-value/rank нужны соответствующие owner-bound основания. Missing cost не стирает supported gross; supplied compatible CAP-03 cost позволяет отдельно проверить net/ENBS.

**Distinguishing negative.** Отсутствующий обязательный model input (utility, observation law, population/horizon для selected estimand) не заменяется числом. Полностью заданные hypothetical inputs сохраняют conditional result с исходными limits, но не authority. Entropy/compute VOI или caller ranking не становятся decision EVSI. Missing cost ограничивает net/ENBS/cost-sensitive rank, missing capacity/window/deadline — feasibility/resource-constrained rank; ни то ни другое само не уничтожает gross EVSI. Неизвестное перекрытие observations не объявляется независимостью.

**Matched removal.** Native binding-substitution controls с включённым recomputing consumer и сохранёнными metric/ranked markers: удалить owner decision для supported policy-value/rank use или подменить measure/expected cost — consumer пересчитывает затронутый результат либо typed refuses/limits, не сохраняет прежний green. Отдельно сменить utility/likelihood при прежнем artifact; снять cost — withheld net/cost rank при сохранении supported gross; снять capacity — withheld feasibility/constrained rank. Эти controls не заменяются одним likelihood-тестом и не выдаются за code-guard removal; conditional estimate сохраняет свои явно заданные assumptions.

**Граница контекста.** One sequence retains formula-to-artifact-to-consumer; do not split arithmetic from use or merge cost ownership into VOI.

## Первые действия и передача

1. Перечислить весь фактический набор `metric_residual_granularity_not_supported` rows после E02; исторические 15 — baseline, не лимит. Для каждой строки зафиксировать target decision, supported/conditional basis и отсутствующие inputs. Готовый обоснованный subset не ждёт всех остальных.
2. Atlas/DS15 scope owner с P0/root commissions native metric owner. DEB-13 находит существующий producer либо готовит конкретное extension proposal и owner decision; не возвращает отсутствие внутреннего кода как external hold. Выбрать estimand, alternatives, utility/units, prior, observation law, population и horizon.
3. Задать small independent oracle и tolerance, zero-information и changed-input cases; explicit hypothetical inputs отделить от qualified policy-value basis. CAP-03 cost связывается только для net/cost use, capacity — только для feasibility/constrained rank.
4. Persist source-bound metric/refusal и прочитать его fresh DS15/UI-17 consumer; проверить owner/measure/cost/capacity falsifiers и отдельный outcome каждой исходной строки. Joint portfolio использует joint observation law/overlap, не сумму standalone EVSI; shared model/rank owners не дублируются.

**Ответственность и handoff.** Native metric owner владеет формулой/artifact и квалифицированным decision basis, CAP-03 — стоимостью, UI-17 — projection. Внутренний commissioning/bridge имеет named engineering owner; реальные law/utility/rights inputs не выдумываются. Conditional gross computation не требует внешнего endorsement, а его число не даёт policy authority.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-13 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `conditional_acceptance_requirements:composition`: Read CAP-03 cost only for selected net/ENBS or cost-sensitive route; gross EVSI is cost-independent and CAP-03 remains sole writer. Consumption mapping only; no blanket start edge.<br>Source: `task.conditional_acceptance_requirements[0]`.<br>Условия: Selected metric claims ENBS/net value or a cost-sensitive ranking/action using the selected WDI route |
| Supplier [UI-17](../../parents/UI-17.md) | `acceptance:composition`: Compose actual UI-17 acquisition-route acceptance of the persisted supported VOI result/refusal and selected-route basis; cost remains conditional for net/ENBS/cost-sensitive use, and this is not a new preparation/start gate. Machine refs: `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/106/acceptance_dependencies/0`; supplier task `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/64`; declared native owner paths `policy-engine/docs/plans/active/post-e02-r9-unified-implementation/tasks.json#/tasks/64/owner_paths`. The canonical task assigns no concrete output artifact path; bind the actual source/input/backend-bound result during the scoped E02 or FINAL-REVIEW rebind.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-13`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This parent-local source fragment belongs to the named bounded card.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `task.acceptance_evidence_requirements[0]`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`; `solution.implementation_steps[5]`; `solution.implementation_steps[6]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.acceptance_discriminators[4]`; `solution.acceptance_discriminators[5]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`; `solution.input_resolution_rule`
- **execute** — Primary accountability is DEB-13.ds15-numeric-voi (execute) for this parent’s source-defined R19 consumer slice: Compute EVSI only on a supported commissioned basis. The embedded question_id R18-D08-Q03 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[0]` (`R18-D08-Q03`); `task.r19_extension.question_ids[0]` (`R18-D08-Q03`)
- **execute** — Primary accountability is DEB-13.ds15-numeric-voi (execute) for this parent’s source-defined R19 consumer slice: Bind gross metric to stated decision/utility, prior and observation law, target, version/error; cost only for net/ENBS. The embedded question_id R18-D09-Q04 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[1]` (`R18-D09-Q04`); `task.r19_extension.question_ids[1]` (`R18-D09-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
