# CAP-06.solver-call-boundary — Ограничить каждый внешний вызов внутри solver

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [CAP-06](../../parents/CAP-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each selected effectful solver/map evaluation is separately bound, authorized and reconcilable; replay cannot turn an uncertain effect into a fresh observation or success.

**Предпочтительное решение.** Wrap the existing solver evaluation seam with native LIF-04 intent/attempt and LIF-05 rights per effectful call. Freeze acquisition before replayable maps when possible; retain existing solver/provider owners.

**Граница владельца.** Solver/method owner keeps scheduling and numerical meaning. LIF-04 alone owns durable intent/effect/recovery; CAP-06 binds every selected call. LIF-05 owns rights/reservations. No second queue/optimizer/status plane. Parent lease: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Selected solver/effect domain; exact roots/executable/recipient; stable native intent; LIF-04 recovery; LIF-05 permission; private roster where selected.

**Выход и consumer.** Per-evaluation call-to-intent/effect link and admitted/pending/indeterminate result read by existing fresh solver/composition consumer.

**Что можно готовить независимо.** Resolve the actual solver call seam and effect/replay semantics independently. Bind intent before an effectful evaluation; bind roster/private-inference qualification only when its selected federated/private profile requires it.

**Где результат соединяется с другими.** Each selected effectful call consumes LIF-04 intent/effect reconciliation and LIF-05 applicable rights. Consume private-input roster/inference qualification only for a selected federated/private profile; ordinary public/local-input calls do not require that private receipt. Numerical success proves neither statistical inference nor remote completion.

**Positive.** Effectful evaluation is allowed before dispatch, reconciles same intent on retry and reaches composition once.

**Distinguishing negative.** Hidden Jacobian/multistart/map call, duplicate charge, lost response, dropout or retry-until-favorable cannot remain green.

**Matched removal.** Remove per-call wrapper while markers remain; real solver consumer catches unbound call or stays indeterminate.

**Граница контекста.** R15/R16 apply the boundary to every evaluation, not only dispatch/retry; this consumes LIF-04/LIF-05 and the existing solver.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted provider/source rebind where relevant; parent stage remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:interface_agreement; acceptance:composition`: Consume exact selected input roots at private/provider/effectful solver calls.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume exact admitted roots/current-use identity at input, dispatch, call and output admission.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:interface_agreement; acceptance:composition`: Consume durable intent/effect for provider operations and each effectful solver call.<br>Source: `task.depends_on[3]`; `task.acceptance_dependencies[2]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement; acceptance:composition`: Consume shared rights/AP07 outcome at input, dispatch, calls, resume and sinks.<br>Source: `task.depends_on[4]`; `task.acceptance_dependencies[3]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-06.private-input](../../cards/CAP-06/private-input.md) | Required only if this evaluation selects a federated/private profile needing its roster, dropout or inference qualification. Public/local-input evaluations retain their actual effect and rights boundaries without a private-input receipt. |
| Composition output (не start gate) [CAP-06.remote-effect-reconciliation](../../cards/CAP-06/remote-effect-reconciliation.md) | Only for the selected remote operation: persist intent before dispatch, then reconcile observed response/effect after the call. An unknown effect stays indeterminate and cannot justify blind replay. A completed response receipt is not a prerequisite for the first call; private roster qualification applies only when this operation actually uses the private/federated profile. |
| Composition output (не start gate) [CAP-06.rights-and-output-sinks](../../cards/CAP-06/rights-and-output-sinks.md) | At each actual protected input or result sink, consume its current rights and allowed projection. A public/non-federated solver does not require a private participant roster; no selected operation may bypass its applicable rights contract. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Every Jacobian/multistart/map evaluation has an effect boundary; U021’s poisoned-input clause is supplied by private-input, and exact effect by provider/LIF-04.
  `task.r15_extension.adversarial`; `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`
- **join** — The removal clause tests actual roster/use/effect/fence together; solver card consumes private-input, remote-effect and LIF-05 outputs without owning them.
  `task.r16_extension.removal`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
