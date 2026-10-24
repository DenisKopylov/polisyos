# DES-10.numerical-methods — Проверить выбранные численные и повторные методы

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-10](../../parents/DES-10.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected native numerical, trajectory or study method agrees with its independent method-scoped oracle and reexecutes/selectively limits correctly on the exact bound basis/profile.

**Предпочтительное решение.** Use GYD-20 and selected GYD-30/31 plus DES-03/11/12 outputs. Bind exact method/profile/version, trial, changed-basis control, model set, uncertainty, actual cost and failure denominator. Correctness and useful design stay distinct; no universal solver comparison or second replay wave.

**Граница владельца.** DES-10 owns the comparison recipe/output only. GYD-20/30/31, DES-03/11/12 keep numerical/trial/trajectory/study ownership and their own independent oracles. DES-10 does not take a native evaluator lease; resource:replay-profile/{selected_profile} is selected by actual accepted profile.

**Входы.** Actual trials/results, selected method/profile/version, independent small oracle and changed-basis control; exact selected model/trajectory/study outputs.; Reconciled costs/failure denominator and actual native invocation/accepted realization; seed/configuration alone is not live execution.

**Выход и consumer.** Method-scoped numerical/reexecution report with uncertainty, unsupported dimensions, stale-basis/changed-basis result, actual consumer refs and exact costs.

**Что можно готовить независимо.** Select exact claims/profiles and independent oracles; freeze clean-vs-selective and changed-basis controls. All R25 numerical/trajectory/study endpoints join the one FINAL-REPLAY only when their source contracts select them.

**Где результат соединяется с другими.** Consume actual selected owner outputs in FINAL-REPLAY under the actual FINAL-REVIEW immutable reviewed identity and join their fresh numerical readers; no seed/marker-only live result and no universal ranking across methods; this composition does not block independent preparation or owner readiness.

**Positive.** Independent oracle agrees within declared method guarantee; a material basis change changes only affected results; a bounded study design distinguishes the selected rival without fabricated return.

**Distinguishing negative.** Wrong units, omitted model/rival, hidden weight, stale basis, unsupported solver assumption, uncontrolled stochastic retry, false feasibility or default probability cannot pass.

**Matched removal.** Remove an actual trial, required model completion or changed-basis input but keep score/certificate markers; the fresh numerical reader detects the loss.

**Граница контекста.** R25 campaign 3 covers selected numerical/reexecution/trajectory/study correctness. Study permission, actual study return and effect activation remain separate conditional properties; this is not a universal method benchmark.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: Each selected campaign consumes FINAL-REVIEW’s actual final immutable reviewed identity when its campaign result is composed in the original single FINAL-REPLAY wave. This is the canonical acceptance dependency at composition; frozen cases, local oracles, protocol work and owner readiness may proceed independently, with no new ready/start blocker.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DES-10`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — R15 technical-method profiles select the exact numerical/reexecution route; each remains case/method qualified and is not a universal solver benchmark.
  `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.technical_profiles[3]`; `task.r15_extension.technical_profiles[4]`; `task.r15_extension.technical_profiles[5]`; `task.r15_extension.technical_profiles[6]`; `task.r15_extension.technical_profiles[7]`
- **join** — R16 quality case Q01 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[0]`
- **join** — R16 quality case Q02 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[1]`
- **join** — R16 quality case Q03 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[2]`
- **join** — R16 quality case Q04 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[3]`
- **join** — R16 quality case Q05 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[4]`
- **join** — R16 quality case Q06 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[5]`
- **join** — R16 quality case Q07 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[6]`
- **join** — R16 quality case Q09 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[8]`
- **join** — R16 quality case Q12 is checked by its capability-home campaign numerical-methods; its actual native supplier/output is consumed and the quality reference alone is not a passing witness.
  `task.r16_extension.quality_cases[11]`
- **join** — Independent oracle checks deterministic/stochastic family coverage and adaptive-look semantics.
  `task.r19_extension.question_slices[3]` (`R18-D07-Q01`); `task.r19_extension.question_ids[2]` (`R18-D07-Q01`)
- **join** — Replay checks actual coalition values/efficiency with I separately labeled.
  `task.r19_extension.question_slices[4]` (`R18-D07-Q02`); `task.r19_extension.question_ids[3]` (`R18-D07-Q02`)
- **join** — Recompute support inventory under same boundary; unsupported SCI completeness stays limited.
  `task.r19_extension.question_slices[20]` (`R18-D19-Q05`); `task.r19_extension.question_ids[19]` (`R18-D19-Q05`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[12]` — Apply relevant method dimensions under shared denominator. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[19]` — Report numerical correctness separately. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
