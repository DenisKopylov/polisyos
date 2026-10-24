# DES-12.optional-economics — Оценивать численную ценность исследования только при данных

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-12](../../parents/DES-12.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** If selected and supported, gross EVSI, cost-based net value, capacity-based feasibility and compute VOI remain distinct conditional outputs; missing numeric premises never block a justified bounded acquisition route.

**Предпочтительное решение.** Reuse existing decision-value/cost/resource consumers. Compute prospective numeric EVSI before the acquisition decision only from a qualified predictive outcome/likelihood model, current evidence, declared target/decision and justified prior/payoff basis. Actual study return may later update or validate that estimate; it is not an input prerequisite for prospective EVSI. Keep scientific EVSI separate from compute VOI, costs and capacity. Do not schedule, invent numbers or require EVSI for all acquisition.

**Граница владельца.** DES-12 owns the optional consumer route only. Existing DEB-13 owns decision value, DES-04 owns N7 acquisition bridge, existing resource/cost owners supply costs/capacity, and study-return supplies actual result. This card has no scheduler or numeric-owner lease.

**Входы.** Study-design candidate plus current evidence and a qualified pre-study predictive outcome/likelihood model, target, decision utility and justified prior/payoff basis for prospective EVSI.; Actual study-return output only for post-result update/validation or separately labeled realized value, when available.; Explicit actual cost/capacity basis only for net value, cost-sensitive ranking or feasibility; otherwise withhold those dimensions.

**Выход и consumer.** Optional prospective gross EVSI from pre-study predictive inputs, and where applicable a separately labeled post-result update/validation; only with supported cost/capacity, distinct net value/cost rank/feasibility. Missing assumptions remain explicit.

**Что можно готовить независимо.** Prepare optional method and negative controls independently. Prospective numeric EVSI requires validated pre-study predictive inputs; if absent, omit/limit the number and preserve a justified qualitative/bounded acquisition route. Actual return may update or validate a prior estimate, not retroactively create its pre-study basis. Do not block study design or justified acquisition on missing priors, cost or capacity.

**Где результат соединяется с другими.** The fresh DEB-13/DES-04 next-choice consumer may use supported prospective EVSI before the acquisition decision. After the study, actual return may update/validate that estimate or support a separately labeled realized value. Actual return is not a prerequisite for prospective EVSI; costs/capacity join only their respective net/rank/feasibility claims.

**Positive.** A qualified predictive model/current evidence and declared decision basis support a prospective gross EVSI before study selection; a later qualified return updates or validates it. With no cost/capacity, gross value can remain conditional while net priority and feasibility are withheld.

**Distinguishing negative.** Invented priors/payoffs, unsupported predictive likelihood, post-hoc outcomes substituted for prospective EVSI, overlapping standalones summed as independent, gross EVSI promoted to net priority, or compute profile treated as study permission cannot pass.

**Matched removal.** Remove the predictive outcome/current-evidence binding while retaining EVSI markers: prospective numeric EVSI is withheld. A later actual result may be labeled separately but cannot repair the missing pre-study basis. Remove cost/capacity: withhold only net/cost rank/feasibility; removing EVSI still leaves the justified bounded acquisition route.

**Граница контекста.** R25 slice 4 remains optional. Prospective EVSI uses qualified pre-study predictive outcomes/current evidence and a declared decision basis; returned evidence can update or validate it later. Cost, capacity and compute VOI stay separate. No EVSI or scheduler is required for all acquisition.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-06](../../parents/CNT-06.md) | `direct:interface_agreement`: Provides claim/decision target for study design and claim binding for actual returns; only if numeric EVSI is selected, provide current claim/target evidence needed to qualify pre-study predictive inputs. CNT-06 retains claim/evidence ownership.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DEB-13.ds15-numeric-voi](../../cards/DEB-13/ds15-numeric-voi.md) | `interface_reference:reference_only_no_new_gate`: Only when numeric scientific EVSI is selected, consume DEB-13’s existing commissioned decision-value/estimand and predictive-model basis; DEB-13 retains the metric producer. Its absence does not block qualitative/bounded design or justified acquisition.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance. |
| Composition output (не start gate) [DES-12.study-design](../../cards/DES-12/study-design.md) | Only for selected prospective numeric EVSI/feasibility; use a qualified predictive outcome model and declared prior/payoff/decision basis. |
| Composition output (не start gate) [DES-12.study-return](../../cards/DES-12/study-return.md) | Only when updating or validating with an actual returned result; not required for prospective EVSI. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-12`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Bind actual return to next choice; gross EVSI, cost-based net value and capacity feasibility need distinct premises and no scheduler. The actual supplier/consumer remains native; the input clause does not appoint an owner or grant.
  `task.r19_extension.question_slices[8]`
- **execute** — Only selected numeric EVSI is computed; invented priors/payoff fail, while bounded acquisition remains useful without it. The actual supplier/consumer remains native; the input clause does not appoint an owner or grant.
  `task.r19_extension.question_slices[13]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[8]`; `task.r19_extension.question_ids[13]`
- **join** — Removal clause explicitly says EVSI is optional; ensure actual discrimination/result bridge remains the useful route with or without numerical economics.
  `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
