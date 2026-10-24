# CNT-07.capacity-feasibility — Связать external capacity с feasibility без обещаний

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CNT-07](../../parents/CNT-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Feasibility names operating entity, time horizon, staffing/budget/schedule/resources and measured/planned/committed/executed status; constraints remain non-compensable only when selected authority says so.

**Предпочтительное решение.** Reuse GYD-30 as the existing joint capacity/feasibility consumer of operator/technical-authority evidence, resource basis and any selected mandate constraint. GYD-30 does not issue operational capacity or commitments; later execution evidence stays distinct from a plan.

**Граница владельца.** GYD-30 owns the capacity mechanism and native canonical lease as a joint capacity/feasibility consumer; the named operator/technical authority supplies operational facts and any commitment. CNT-07 binds/consumes the qualified result and does not issue capacity or create a competing engine. Exact path/semantic overlaps unresolved after E02; do not assume disjoint.

**Входы.** Named operating entity, technical authority, resource basis and time horizon; mandate-evidence only when actual constraint requires it.

**Выход и consumer.** GYD-30 owner-qualified joint capacity/feasibility relation, carrying supplied commitment status only when evidenced, with affected design links; read by the selected G4/G5 feasibility consumer. GYD-30 does not issue an operational commitment.

**Что можно готовить независимо.** Can identify read-only GYD-30 route; no capacity is inferred until real operator evidence, E02 binding, native lease and permit.

**Где результат соединяется с другими.** Fresh G4/G5 feasibility/constrained-rank consumer reads GYD-30 output and separately qualified mandate constraint.

**Positive.** Documented capacity under named horizon changes feasibility; unknown stays unknown.

**Distinguishing negative.** Promise/headcount/CI is treated as slot; turnover is treated as capacity change; testimony as measured capacity.

**Matched removal.** Remove owner-qualified capacity/time/resource basis but keep labels: affected feasibility becomes unknown; unrelated values/evidence remain.

**Граница контекста.** Existing GYD-30 is mechanism owner. R15 capacity/value joint clause is received as feasibility and consumes distinct mandate evidence.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Case scope, selected audience/remit, actual answerer roles and relevant claims.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Selected source identity/version route where relevant; metadata is not consent, mandate or capacity.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CNT-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — R15 requirement combines incumbent capacity with preference/mandate grounds; feasibility is accountable receiver and consumes separately qualified mandate-evidence.
  `task.r15_extension.requirement`
- **join** — R15 combines incumbent capacity with an authorized non-compensable constraint; feasibility consumes the separate mandate-evidence output and actual operator facts.
  `task.r15_extension.positive`; `task.r15_extension.adversarial`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `task.r19_extension.question_slices[9]`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `task.r19_extension.question_slices[11]`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `task.r19_extension.question_slices[14]`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `task.r19_extension.question_ids[9]`
- **join** — This slice explicitly distinguishes testimony from measured capacity and names GYD-30 as existing capacity owner; feasibility consumes a separate permitted account if selected.
  `task.r19_extension.question_ids[14]`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `solution.composition_contracts[1]`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
