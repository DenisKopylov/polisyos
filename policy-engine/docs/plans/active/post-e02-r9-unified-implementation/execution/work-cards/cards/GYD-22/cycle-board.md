# GYD-22.cycle-board — Собрать пять сигналов в Cycle Board

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [GYD-22](../../parents/GYD-22.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Existing G8 board projects T1/T2/T3/T6/T7 with source, time, denominator, uncertainty, missingness and unresolved normative remainder.

**Предпочтительное решение.** Wire or extend the existing G8 health metric and Cycle Board owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-22's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing G8 health metric and Cycle Board owner.

**Входы.** five signal-card outputs; G8 metric snapshots and accepted definitions; DES-10 quality/diversity/cost/false-abstention diagnostics as descriptive context, never a useful-design-rate promotion objective

**Выход и consumer.** Five-signal Cycle Board projection

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh current G8 board reader. This is the only multi-signal composition card; signal owners stay separate.

**Positive.** All five named signals resolve with their owner meaning.

**Distinguishing negative.** Missing source is visible, not zero; correlation is not causal; no global threshold.

**Matched removal.** Remove measurement or predeclared causal contrast; board shows missing/unknown or drops unsupported claim.

**Граница контекста.** This is the only multi-signal composition card; signal owners stay separate.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted metric definition and owner mapping consumed by the existing board reader.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [DES-10.productivity](../../cards/DES-10/productivity.md), [DES-10.numerical-methods](../../cards/DES-10/numerical-methods.md) | `interface_reference:reference_only_no_new_gate`: Read selected DES-10 productive-quality/diversity/cost/false-abstention outputs as descriptive context for the board; no useful-design-rate promotion objective or gate.<br>Source parent `DES-10`: `task.deliverable`.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |
| Composition output (не start gate) [GYD-22.envelope](../../cards/GYD-22/envelope.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh current G8 board reader. This is the only multi-signal composition card; signal owners stay separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [GYD-22.semantic-loss](../../cards/GYD-22/semantic-loss.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh current G8 board reader. This is the only multi-signal composition card; signal owners stay separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [GYD-22.throughput](../../cards/GYD-22/throughput.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh current G8 board reader. This is the only multi-signal composition card; signal owners stay separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [GYD-22.demand-abstention](../../cards/GYD-22/demand-abstention.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh current G8 board reader. This is the only multi-signal composition card; signal owners stay separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [GYD-22.recall-staleness](../../cards/GYD-22/recall-staleness.md) | Only for the selected same-scope composition described by this card: Fresh consumer: fresh current G8 board reader. This is the only multi-signal composition card; signal owners stay separate. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-22`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — The task-level five-signal result, positive/adversary/removal/surface and history are read at the existing multi-signal board.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **join** — Preferred solution and first three steps name all five signals, T1/T6/T7 collision resolution, matching V2/V3 snapshots and denominator/missingness/hash/uncertainty projection.
  `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`
- **binding** — Causal claims need a predeclared same-case contrast; otherwise this remains descriptive.
  `solution.implementation_steps[4]`
- **binding** — Signal growth, owner definitions, history, plural outcomes, search-ceiling evidence, missingness, measurement removal and partial reporting are composed at board.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`
- **join** — The cycle-board card owns the single generic per-ID row that links the five descriptive signals to G8 evidence-only answers or to evidence/options plus an open normative remainder; no signal decides design.
  `task.r19_extension.question_slices[0]` (`R18-D23-Q03`); `task.r19_extension.question_ids[0]` (`R18-D23-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
