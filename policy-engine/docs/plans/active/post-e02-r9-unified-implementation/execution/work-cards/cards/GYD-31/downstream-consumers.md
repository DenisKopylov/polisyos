# GYD-31.downstream-consumers — Проверить set-valued S1/N8/N6 consumers

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [GYD-31](../../parents/GYD-31.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Actual S1, N8 and N6 use principal-specific sets, preserve partial/reversal/incomparability and do not choose collective winner or implicit weight.

**Предпочтительное решение.** Wire or extend the existing PDC consumers and set-valued valuation/comparison path; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-31's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing PDC consumers and set-valued valuation/comparison path.

**Входы.** persisted ValueOuterSet; all trust/identification/assumption/calibration/WMR/epoch fields

**Выход и consumer.** Fresh S1/N8/N6 set-semantic readback

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual valuation/comparison consumers. Bounded set operations return unknown/blocked on evidence/resource shortfall.

**Positive.** Matched evidence narrows only its justified component; conditional sets remain available without mandate.

**Distinguishing negative.** Missing status/sample/timeout/trust downgrade remains blocked/unknown.

**Matched removal.** Remove set operations but keep markers; oracle exposes false point or selected winner.

**Граница контекста.** Bounded set operations return unknown/blocked on evidence/resource shortfall.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Composition output (не start gate) [GYD-31.value-set](../../cards/GYD-31/value-set.md) | Consume only for the exact composition described here: Fresh consumer: actual valuation/comparison consumers. Bounded set operations return unknown/blocked on evidence/resource shortfall. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-31`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Task delivery, positive/adversary/removal/surface require actual consumer readback.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`
- **binding** — Preserve vector objectives and incomparable/model-sensitive choices in DES-03/06 without implicit social weight or scalar promotion.
  `task.r14_extension.requirement`
- **execute** — Keep statistical/identification/numerical/model/value uncertainties distinct; narrow only justified component; reject solver signal as truth; exercise target/assumption/value-separation removal.
  `task.r15_extension.requirement`; `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`
- **execute** — Valuation/comparison operate on set and probe missing status/sample/timeout/trust/removal.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`
- **binding** — Bounded operations and evidence shortage return unknown/blocked.
  `solution.free_grow.resource_behavior`
- **execute** — Owner-derived width and semantic fields reach current readers; width/missing/removal/consumer-collapse behavior is tested.
  `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`
- **execute** — The actual S1/N8/N6 readers must preserve principal-specific partial, reversed, and incomparable sets as conditional results without choosing a collective winner or implicit weight.
  `task.r19_extension.question_slices[0]` (`R18-D05-Q01`); `task.r19_extension.question_ids[0]` (`R18-D05-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
