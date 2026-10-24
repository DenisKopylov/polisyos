# DES-11.trajectory-run — Выполнить условную траекторию на наблюдаемой истории

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-11](../../parents/DES-11.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The native temporal evaluator persists conditional policy paths for action order, observable histories, lag/carryover, incumbents, capacity and residual commitments using only information available at each decision time.

**Предпочтительное решение.** Extend the native candidate/temporal evaluation bridge; reuse accepted-source implementation and selected method. Bind declared clocks/events, participant state recovery, nonanticipativity, suffix replay and method-qualified stochastic/equilibrium rules. Warm start is only a guess absent a stronger equivalence proof.

**Граница владельца.** DES-11 owns only write:native-temporal-evaluation under the selected method resource/profile. DES-03 remains Scientist search writer; GYD-30 owns joint witness and any shared joint result/API path; DES-04 owns feedback/acquisition. No parallel adaptive-policy engine or simulator.

**Входы.** history-context’s bound observable history, cutoffs, actual/assumed incumbents and capacity basis.; Accepted native intervention/operator/method and selected resource permit; actual method output/state recovery or explicit unsupported/limited result.

**Выход и consumer.** Persisted, versioned conditional trajectory/path evaluation with transitions, action order, observed branch, residual obligations, uncertainty, selected method, costs and unsupported dimensions.

**Что можно готовить независимо.** The adapter and controlled order/delay/no-op/stop oracles may be prepared independently against the agreed history/evaluator interfaces after E02 source rebind. Actual execution uses the selected method/resource and joins actual history context; no future/latent state or universal equilibrium guarantee.

**Где результат соединяется с другими.** Persisted result is consumed by the existing fresh Scientist frontier/dossier reader; any search-space or shared joint-result change is requested from DES-03/GYD-30 respectively.

**Positive.** A controlled A-then-B versus B-then-A case differs only after observable histories diverge; residual commitments and delayed effects remain in the compared path.

**Distinguishing negative.** Clairvoyance, backdated knowledge, noisy signpost interpreted as no harm, truncated tail, global incumbent replacement, assumed capacity, lucky sampled equilibrium or ungrounded horizon discount cannot support a feasible recommendation.

**Matched removal.** Keep adaptive labels but remove actual history/transition/cutoff/incumbent/capacity consumption; independent path and feasibility oracle fails or limits the result.

**Граница контекста.** The actual observable-history context joins the selected native evaluator; adapter and oracle preparation is independent. This card does not own search, joint simulation, capacity authority, external execution or posterior activation.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DES-03](../../parents/DES-03.md) | `direct:interface_agreement`: Consumes accepted candidate/search basis for selected trajectory and the resulting frontier composition; DES-03 remains search writer.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-30](../../parents/GYD-30.md) | `direct:interface_agreement`: Consumes actual joint simulation/result interface; GYD-30 retains sole joint witness and shared API ownership.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DES-11.history-context](../../cards/DES-11/history-context.md) | Only for the selected same-scope composition described by this card: Persisted result is consumed by the existing fresh Scientist frontier/dossier reader; any search-space or shared joint-result change is requested from DES-03/GYD-30 respectively. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-11`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The deliverable is the actual conditional temporal evaluation producer; history-context and frontier-consumer are its explicit input and reader checkpoints.
  `task.deliverable`
- **join** — Future leakage, late knowledge, noisy signal, tail, incumbent and capacity clauses falsify actual path execution; actual history context is consumed, not guessed.
  `task.adversarial`
- **execute** — R16 adapter binds clocks/events, full participant-state recovery, nonanticipativity and suffix replay; warm start remains a guess unless equivalence is proved.
  `task.r16_extension.requirement`
- **join** — R16 adversarial/removal clauses test hidden state, clocks, reset, selected root and method/error guarantee on the actual evaluator.
  `task.r16_extension.adversarial`; `task.r16_extension.removal`
- **binding** — R16 delivery/quality references are scoped trajectory-execution cases; their actual source/method outputs remain conditional and method-qualified.
  `task.r16_extension.delivery_slices[0]`; `task.r16_extension.delivery_slices[1]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`
- **join** — R17 mixed incumbent/exposure/announcement/carryover clauses exercise actual path execution; planned versus external observed branches remain distinct.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **binding** — R17 delivery/quality references map to actual selected temporal method and incumbent execution; GYD-30 retains joint witness.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`
- **join** — Use actual action order and separate act/receipt/operation; late correction reruns affected suffix without rewriting as-known state. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[0]`
- **join** — Keep search stopping distinct from conditional action paths; A→B/B→A depend on observed history, not seed/order noise. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[3]`
- **join** — Source/method-qualified path displacement is conditional; DES-11 is not causal/legal source owner. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[6]`
- **join** — Bounded joint schedule/profile/horizon uses actual counterfactual support; a response label alone is insufficient. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[7]`
- **join** — Keep horizon vectors distinct from optional assumption-bound scalar comparisons; no default discount becomes a case fact. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[8]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.question_ids[6]`; `task.r19_extension.question_ids[7]`; `task.r19_extension.question_ids[8]`
- **execute** — Preferred native path is the selected temporal evaluator, with exact history and consumer siblings named.
  `solution.preferred_solution`
- **execute** — Numbered DES-11 method steps belong to actual trajectory evaluator while inheriting all authority/time/activation boundaries.
  `solution.implementation_steps[1]`
- **join** — Adversarial path/capacity/model leakage falsifies execution on the selected method, not a terminal marker.
  `solution.acceptance_discriminators[1]`
- **join** — Removal of history/transition/cutoff/incumbent consumption must fail the independent path oracle.
  `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
