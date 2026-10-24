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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Inherited accepted E02 readiness and scoped source rebind apply to each listed card; no extra start gate is added, and canonical parent stage/dispatch remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-01](../../parents/CNT-01.md) | `direct:owner_readiness`: Case scope, selected audience/remit, actual answerer roles and relevant claims.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-02.source-profile](../../cards/CNT-02/source-profile.md) | `direct:interface_agreement; acceptance:composition`: Selected source identity/version route where relevant; metadata is not consent, mandate or capacity.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CNT-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **join** — R15 requirement combines incumbent capacity with preference/mandate grounds; feasibility is accountable receiver and consumes separately qualified mandate-evidence.
  `task.r15_extension.requirement`
- **join** — R15 combines incumbent capacity with an authorized non-compensable constraint; feasibility consumes the separate mandate-evidence output and actual operator facts.
  `task.r15_extension.positive`; `task.r15_extension.adversarial`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `solution.composition_contracts[1]`
- **execute** — These clauses distinguish measured/planned/committed/executed capacity, operator resources and testimony from actual capacity; GYD-30 stays the mechanism owner.
  `solution.acceptance_discriminators[2]`
- **execute** — Capacity-feasibility binds sourced operational slots, time horizon and commitment state through the existing GYD-30 owner; mandate or testimony is not capacity. Slice: Source capacity/window/deadline for feasibility; distinguish planned/committed/executed. Positive discriminator: Sourced slot changes feasibility, not gross EVSI. Adversary: Promise/headcount/CI is not a slot; absent capacity blocks feasibility/constrained rank only. Removal: Drop capacity link; feasibility/constrained rank changes, gross EVSI does not.
  `task.r19_extension.question_slices[9]` (`R18-D09-Q04`); `task.r19_extension.question_ids[9]` (`R18-D09-Q04`)
- **execute** — Capacity-feasibility binds sourced operational slots, time horizon and commitment state through the existing GYD-30 owner; mandate or testimony is not capacity. Slice: Separate mandate evidence from current inputs/execution; bind period, scope, source. Positive discriminator: Authority transfers with stable capacity; lost coverage limits feasibility only. Adversary: New signature means capacity, or turnover means capacity loss. Removal: Remove resource relation but retain actor labels: feasibility consumer refuses.
  `task.r19_extension.question_slices[11]` (`R18-D22-Q04`); `task.r19_extension.question_ids[13]` (`R18-D22-Q04`)
- **execute** — Capacity-feasibility binds sourced operational slots, time horizon and commitment state through the existing GYD-30 owner; mandate or testimony is not capacity. Slice: Use existing GYD-30 owner; bind actual supply separately from testimony/mandate. Positive discriminator: A sourced commitment reduces remaining supply. Adversary: Testimony is mislabeled measured capacity. Removal: Remove supply basis; fresh joint result is limited.
  `task.r19_extension.question_slices[14]` (`R18-D20-Q02`); `task.r19_extension.question_ids[12]` (`R18-D20-Q02`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[7]` — Limit feasibility conclusions affected by operator/technical-authority interest. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
