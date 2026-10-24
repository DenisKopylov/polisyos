# DES-12.study-design — Спроектировать различающий исследовательский маршрут

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [DES-12](../../parents/DES-12.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A versioned feasible candidate study distinguishes decision-relevant rival explanations with explicit target, sampling/assignment, measurement, analysis, stopping and denominator; identifiability, estimability and decision relevance remain separate.

**Предпочтительное решение.** Extend existing CausalExperimentDesigner/ExperimentPlan and native acquisition/causal workflow. Design over rival structures, observation regimes and selected exposure history; provide qualitative bounded design/refusal without fabricated defaults. No universal study DTO or autonomous executor.

**Граница владельца.** DES-12 owns native study design under write:native-causal-study-design. DES-03 remains search writer, DES-04 feedback/acquisition bridge writer, GYD-30 joint witness owner and CNT-06 claim/case owner. Design is not permission or evidence activation; exact path lease must be E02-rebound.

**Входы.** CNT-06 actual claim/decision basis and selected outcome/target; DES-03 model-sensitive candidate alternatives only when present.; Explicit/content-bound inputs or declared hypothetical assumptions; do not turn default probabilities/payoff/mandate into case facts.; Selected method/resource profile; computation permit is not a data/study permission.

**Выход и consumer.** Versioned study candidate with rival/model set, estimand/target, feasible sampling and assignment, measurement, analysis/stopping, denominator, observation regime and explicitly unresolved assumptions.

**Что можно готовить независимо.** Internal design/analysis/adapter may proceed after E02 source rebind and agreed interfaces. A bounded qualitative design is useful without numeric EVSI or an actual external study; execution remains a separate conditional operation.

**Где результат соединяется с другими.** Candidate design can complete on its own. Join study-authorization only for a selected protected dispatch, study-return only after selected owner-conducted study, and optional-economics only when numeric value is selected; none is mandatory for design completion.

**Positive.** An independently specified observationally equivalent pair receives a feasible design that separates intervention predictions; decision-equivalent alternatives avoid unnecessary acquisition, and limitations remain explicit.

**Distinguishing negative.** Single-graph fallback, uninformative repeated query, mismatched target, post-hoc scenario choice, unsupported static method, default probabilities or missing denominator cannot resolve a contested mechanism.

**Matched removal.** Remove actual rival discrimination, target/method binding or sampling-analysis bridge while retaining protocol fields; the independent design oracle finds no useful distinction.

**Граница контекста.** R25 slice 1 is internal design work. It can be prepared without institutional permission; external study conduct and results are separate conditional joins and do not become a universal executor. Authorization, return and numeric economics are selected-use composition only, not design-completion prerequisites.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CNT-06](../../parents/CNT-06.md) | `direct:interface_agreement`: Provides claim/decision target for study design and claim binding for actual returns; only if numeric EVSI is selected, provide current claim/target evidence needed to qualify pre-study predictive inputs. CNT-06 retains claim/evidence ownership.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DES-12`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Deliverable is internal candidate design plus a returned-result binding; design is owned here and actual authorization/return are separate cards.
  `task.deliverable`
- **join** — R16 model-sensitive design and information-acquisition clauses belong to the candidate discriminator; actual result return and no post-hoc/same-cohort claims remain separate.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.delivery_slices[1]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`
- **execute** — R17 exposure/method-qualified estimand informs the study design and selected target.
  `task.r17_extension.requirement`
- **execute** — Preferred solution is native CausalExperimentDesigner/ExperimentPlan design; authorization, return and optional economics are explicit separate outputs.
  `solution.preferred_solution`
- **execute** — Numbered DES-12 design steps belong to the actual candidate study design and inherit its authority/time/activation constraints.
  `solution.implementation_steps[1]`
- **execute** — Bound study applicability to evidenced population and timeframe.
  `task.r19_extension.question_slices[0]` (`R18-D06-Q01`); `task.r19_extension.question_ids[0]` (`R18-D06-Q01`)
- **execute** — Design discriminator across rival structures; old data fit alone selects no do-effect.
  `task.r19_extension.question_slices[1]` (`R18-D06-Q02`); `task.r19_extension.question_ids[1]` (`R18-D06-Q02`)
- **execute** — Claim scoped robustness only while retained rivals agree under bound/version.
  `task.r19_extension.question_slices[2]` (`R18-D06-Q03`); `task.r19_extension.question_ids[2]` (`R18-D06-Q03`)
- **execute** — Use missing-result risk for design/acquisition; do not impute null as zero.
  `task.r19_extension.question_slices[3]` (`R18-D06-Q05`); `task.r19_extension.question_ids[3]` (`R18-D06-Q05`)
- **execute** — Design target-aligned discriminator for harm versus reporting shift.
  `task.r19_extension.question_slices[10]` (`R18-D10-Q01`); `task.r19_extension.question_ids[10]` (`R18-D10-Q01`)
- **execute** — Design feasible discriminator for transport rival; permission/result stay separate.
  `task.r19_extension.question_slices[11]` (`R18-D10-Q02`); `task.r19_extension.question_ids[11]` (`R18-D10-Q02`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[4]` — Candidate design proceeds independently; authorization binds only selected protected dispatch. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[12]` — Candidate design stays independent of downstream branches. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
