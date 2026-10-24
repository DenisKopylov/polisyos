# OPS-08.research-meter — Считать вложенные вычисления в общем permit

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [OPS-08](../../parents/OPS-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Selected design-search, study-simulation, solver, coupling and composed map work consumes the shared resource permit across nested calls, retries, probes, final materialization and persisted bytes; over-budget work returns an honest incomplete frontier.

**Предпочтительное решение.** Wire the existing LIF-06 admission/usage contract into native Foundry/Scientist search and evaluation call sites. Count complete map evaluations (multi-start, finite-difference/Jacobian, retry, output/checkpoint/CAS bytes); no per-model cap ledger or second scheduler.

**Граница владельца.** G05 method owners retain writes to their own canonical callsites; this OPS card consumes the shared `resource:host/{host}/memory-disk` policy and does not claim a method owner or new source path. Any actual adapter requires its native lease after accepted-source rebind; shared capacity remains serialized by LIF-06.

**Входы.** LIF-06 aggregate permit and usage receipt; Existing G05 search/study/solver/coupling invocation graph and nested-work denominator; Selected host/cap envelope from `class-envelope`

**Выход и consumer.** Usage linked to the existing permit/attempt and method output; terminal result is complete or explicit limited/unrun frontier consumed by the fresh method-result reader.

**Что можно готовить независимо.** Callsite interface can be agreed and instrumentation prepared independently of the LIF-06 implementation; protected execution requires the actual shared permit and complete nested work accounting.

**Где результат соединяется с другими.** The cap is resource availability, not numerical feasibility, policy result, or study EVSI. G05 owners keep search/design semantics; LIF-06 owns aggregate admission; OPS-07 account-spend authority remains separate.

**Positive.** Nested/retried evaluations stay within aggregate cap and retain useful result or a visibly incomplete frontier; independent scenario shards fit the same actual capacity.

**Distinguishing negative.** Each model respects a local cap while aggregate compute/memory exceeds host budget, a timeout is called infeasible, or an external effect is repeated on retry.

**Matched removal.** Remove shared cap/nested work accounting but retain requested limits; controlled contended execution or the incomplete-frontier reader exposes the lost property.

**Граница контекста.** This is a G05 consumer integration, not a new operations scheduler or scientific-result owner. R15 technical profiles are possible methods, not mandatory layers; P02/P10/P13/P29 require a real producer-to-fresh-consumer witness.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: All writers/consumers use the accepted source and task-scoped rebind; preserve parent dispatch, not a new all-task edge.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-06](../../parents/LIF-06.md) | `direct:owner_readiness`: Use the single native aggregate admission/eligibility owner and actual usage receipt; no second shared ledger.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-08.aggregate-cap](../../cards/OPS-08/aggregate-cap.md) | Only for the selected same-scope composition described by this card: The cap is resource availability, not numerical feasibility, policy result, or study EVSI. G05 owners keep search/design semantics; LIF-06 owns aggregate admission; OPS-07 account-spend authority remains separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [OPS-08.class-envelope](../../cards/OPS-08/class-envelope.md) | Only for the selected same-scope composition described by this card: The cap is resource availability, not numerical feasibility, policy result, or study EVSI. G05 owners keep search/design semantics; LIF-06 owns aggregate admission; OPS-07 account-spend authority remains separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-08`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for research-meter; selectors task.r15_extension.detail, task.r15_extension.quality_ref, task.r15_extension.technical_profiles[0], task.r15_extension.technical_profiles[1], task.r15_extension.technical_profiles[2], task.r15_extension.product_verification, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2] remain load-bearing.
  `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.product_verification`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`
- **execute** — Direct result/preferred path for research-meter; selectors task.r15_extension.requirement name the work and native owner seam.
  `task.r15_extension.requirement`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for research-meter; selectors task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.r15_extension.positive, task.r15_extension.adversarial, task.r15_extension.removal, task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2] are checked at its actual reader/sink. Bundled subclauses: U049:{"question_id":"R18-D07-Q01","solution_ref":"solutions/lifecycle-r19/S07.md#r18-d07-q01","mechanism_ids":["S07-M1"],"role":"shared compute owner"}; U050:{"question_id":"R18-D08-Q03","solution_ref":"solutions/lifecycle-r19/S08.md#r18-d08-q03","mechanism_ids":["S08-M3"],"role":"scoped participant; input collection only for this task’s existing owned predicate"}; U051:{"question_id":"R18-D09-Q04","solution_ref":"solutions/lifecycle-r19/S09.md#r18-d09-q04","mechanism_ids":["S09-M4"],"role":"consumer"}.
  `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`; `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
