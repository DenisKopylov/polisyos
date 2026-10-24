# DES-11.history-context — Связать историю наблюдений и действующих обязательств

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-11](../../parents/DES-11.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A trajectory’s decision-time history resolves observable event/receipt/verification/decision cutoffs, incumbent scope, actual/declared capacity, carryover, exposure and unresolved time/retention limits without future leakage.

**Предпочтительное решение.** Reuse native event and incumbent records; keep act, receipt, operation and knowledge-as-of clocks distinct. Carry unknowns explicitly and never infer a path from terminal-only history or treat a planned rollout/capacity as observed fact.

**Граница владельца.** DES-11 consumes existing CNT-06/CNT-07/LIF-02 history, claim and currentness owners under its selected method resource; it does not own those facts or external mandate. Any foundry/execute/api.py or joint-result change remains GYD-30 scope. Exact lease is write:native-temporal-evaluation plus selected method resource, resolved after E02.

**Входы.** CNT-06/CNT-07 claim and case/history refs; LIF-02 event/currentness evidence with event, receipt, verification and decision time.; Actual or explicitly declared assumed incumbent/capacity/transition/observation bounds only for claims that require them; external institution retains authorization and execution.

**Выход и consumer.** Versioned observable-history/cutoff context with incumbent and capacity basis, knowledge-as-of, unresolved dimensions and source refs for the native trajectory evaluator.

**Что можно готовить независимо.** May map native clocks, state recovery and incumbent interfaces after source rebind. Unknown conditions permit a declared conditional candidate but do not become fabricated facts or permission.

**Где результат соединяется с другими.** trajectory-run consumes this context; the frontier consumer consumes its persisted path and limitations. Late correction preserves prior as-known context while current use follows existing LIF invalidation.

**Positive.** Partial rollout and a late correction preserve the old as-known path while refreshing only the supported later suffix; mixed incumbents remain scoped by population/time.

**Distinguishing negative.** Published date as receipt, missing awareness treated as no anticipation, hidden state, candidate ID replacing incumbent scope or permit treated as physical capacity cannot support the history.

**Matched removal.** Remove event/receipt/decision cutoff, actual incumbent/capacity or retention binding while keeping history labels; path oracle rejects or limits the result.

**Граница контекста.** A truthful input/cutoff checkpoint, not an input-supplier appointment. Explicit assumptions allow candidate analysis; authority/currentness gates still use native owner evidence.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-06](../../parents/CNT-06.md) | `direct:interface_agreement`: Consumes actual claim/case/history basis; CNT-06 remains source/claim owner.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-07](../../parents/CNT-07.md) | `direct:interface_agreement`: Consumes native method/claim-relevant evidence interface only where selected; CNT-07 keeps source ownership.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-02](../../parents/LIF-02.md) | `direct:interface_agreement`: Consumes actual event/currentness/receipt clock facts; LIF-02 retains lifecycle ownership.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-11`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Actual capacity/incumbent/transition/observation grounds are conditional input facts; external institutions retain mandate, authorization and execution.
  `task.genuine_external_inputs[0]`
- **binding** — Late correction preserves old lawful as-known context and updates only affected suffix; retention denial is projected honestly.
  `task.r16_extension.positive`
- **join** — Bind verified mixed incumbent scope and declared uncertainty; replacement layers cannot disable the existing incumbent globally. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[1]`
- **join** — Timed discovery changes path only at its supported revision/cutoff; missing narrow-frame signal is not proof of no harm. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[2]`
- **join** — Bind actual receipt, target and observation regime; reporting or rollout changes limit subgroup comparison. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[4]`
- **join** — Use external physical-capacity denominator and incumbent commitments; a one-GPU run permit is not public capacity. Actual event/claim/method supplier remains named in the card; no new DAG edge is inferred.
  `task.r19_extension.question_slices[5]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
