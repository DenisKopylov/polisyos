# CAP-06.solver-call-boundary — Ограничить каждый внешний вызов внутри solver

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [CAP-06](../../parents/CAP-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each selected effectful solver/map evaluation is separately bound, authorized and reconcilable; replay cannot turn an uncertain effect into a fresh observation or success.

**Предпочтительное решение.** Wrap the existing solver evaluation seam with native LIF-04 intent/attempt and LIF-05 rights per effectful call. Freeze acquisition before replayable maps when possible; retain existing solver/provider owners.

**Граница владельца.** Solver/method owner keeps scheduling and numerical meaning. LIF-04 alone owns durable intent/effect/recovery; CAP-06 binds every selected call. LIF-05 owns rights/reservations. No second queue/optimizer/status plane. Parent lease: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Selected solver/effect domain; exact roots/executable/recipient; stable native intent; LIF-04 recovery; LIF-05 permission; private roster where selected.

**Выход и consumer.** Per-evaluation call-to-intent/effect link and admitted/pending/indeterminate result read by existing fresh solver/composition consumer.

**Что можно готовить независимо.** Resolve actual solver call seam and effect/replay semantics; bind roster and intent before map execution.

**Где результат соединяется с другими.** Consume private-input qualification, provider effect receipt and shared rights at each call; numerical success proves neither inference nor remote completion.

**Positive.** Effectful evaluation is allowed before dispatch, reconciles same intent on retry and reaches composition once.

**Distinguishing negative.** Hidden Jacobian/multistart/map call, duplicate charge, lost response, dropout or retry-until-favorable cannot remain green.

**Matched removal.** Remove per-call wrapper while markers remain; real solver consumer catches unbound call or stays indeterminate.

**Граница контекста.** R15/R16 apply the boundary to every evaluation, not only dispatch/retry; this consumes LIF-04/LIF-05 and the existing solver.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted provider/source rebind where relevant; parent stage remains.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:interface_agreement; acceptance:composition`: Consume exact selected input roots at private/provider/effectful solver calls.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume exact admitted roots/current-use identity at input, dispatch, call and output admission.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:interface_agreement; acceptance:composition`: Consume durable intent/effect for provider operations and each effectful solver call.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement; acceptance:composition`: Consume shared rights/AP07 outcome at input, dispatch, calls, resume and sinks.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-06.private-input](../../cards/CAP-06/private-input.md) | Consume only for the exact composition described here: Consume private-input qualification, provider effect receipt and shared rights at each call; numerical success proves neither inference nor remote completion. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [CAP-06.remote-effect-reconciliation](../../cards/CAP-06/remote-effect-reconciliation.md) | Consume only for the exact composition described here: Consume private-input qualification, provider effect receipt and shared rights at each call; numerical success proves neither inference nor remote completion. This link is not an unconditional all-of or preparation gate. |
| Composition output (не start gate) [CAP-06.rights-and-output-sinks](../../cards/CAP-06/rights-and-output-sinks.md) | Consume only for the exact composition described here: Consume private-input qualification, provider effect receipt and shared rights at each call; numerical success proves neither inference nor remote completion. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-06`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Every Jacobian/multistart/map evaluation has an effect boundary; U021’s poisoned-input clause is supplied by private-input, and exact effect by provider/LIF-04.
  `task.r15_extension.adversarial`; `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`
- **join** — The removal clause tests actual roster/use/effect/fence together; solver card consumes private-input, remote-effect and LIF-05 outputs without owning them.
  `task.r16_extension.removal`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
