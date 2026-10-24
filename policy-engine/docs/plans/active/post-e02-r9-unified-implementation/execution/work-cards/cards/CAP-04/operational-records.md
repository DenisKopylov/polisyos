# CAP-04.operational-records — Принять операционные/exposure-записи как входы

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CAP-04](../../parents/CAP-04.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Actual custodian/adopter operational or exposure records remain source-bound measurements with their own scope/time, not a legal act, causal effect or source-change event.

**Предпочтительное решение.** Use the selected source’s existing operation/exposure record path from S13-M1 and R18-D22-Q01/Q04; bind source-native execution/coverage, exact denominator/cut and time roles, then hand only the matching feasibility/currentness predicate to existing LIF-02/DecisionValidityService and CNT-09 readers. This card must map the current repo’s producer→persisted record→fresh reader/surface now; E02 rebinds the accepted path/lease but does not defer discovery.

**Граница владельца.** Institution/custodian owns the original record and interpretation; CAP-04 binds supplied evidence and owns internal discovery of the selected native producer, persisted artifact and actual reader. E02 confirms the accepted path/lease before writes, not before repo reconnaissance. If no chain exists, report the precise absent/unallocated or consumer_missing state. Parent lease: `write:source-event-adapter/{owner}`; exact paths/overlap remain unresolved, with no sibling-disjointness or child lease inference.

**Входы.** Actual operational/exposure/execution record with source, denominator/cut, provenance and recorded/effective/known times; internal anchors S13-M1 and R18-D22-Q01/Q04 for producer/reader discovery.

**Выход и consumer.** Typed candidate record receipt preserving source and measure, plus an internal producer→persisted artifact→fresh reader/surface map or a precise missing-chain state; never directly an LIF-02 event.

**Что можно готовить независимо.** Now trace the current canonical source-cut/operational record producer, persisted artifact and actual LIF-02/CNT-09 reader using S13-M1 and R18-D22-Q01/Q04; record exact repo anchors and which feasibility predicate consumes it.; Use E02 to bind the accepted selected path and parent lease before writes; do not wait for E02 to begin the reader census.; When a real record is selected, separate plan, decision, execution, observation and effect; do not synthesize workforce or event evidence.

**Где результат соединяется с другими.** Only separately qualified source event or bounded observation reaches LIF-02.

**Positive.** Fresh reader resolves authentic source/cut and explicit missing cells.

**Distinguishing negative.** Plan, institution label or aggregate without denominator cannot prove execution or effect.

**Matched removal.** Keep status labels but remove source/cut/denominator binding; reader refuses use.

**Граница контекста.** This input card actively discovers the existing producer and reader in the current repo; external operational evidence remains institution/custodian supplied. E02 rebinds exact paths/lease. If internal discovery finds no consumer, report consumer_missing with the searched native anchors; no monitor or decision owner is created.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted selected owner/path consumed when resolved; original stage gate remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — D4/Q10 and exposure/resource/worker-clock/actual-use facts remain source-bound records; plan, act, execution and worker due time differ.
  `task.r17_extension.delivery_slices[1]`; `task.r17_extension.quality_cases[2]`
- **execute** — bind actual operational/exposure record, denominator/cut, cohort/site/period, provenance, and time; keep the measurement distinct from law, causal effect, or source event.
  `task.r19_extension.question_slices[2]` (`R18-D22-Q01`); `task.r19_extension.question_ids[7]` (`R18-D22-Q01`)
- **execute** — Operational-records supplies the measured source cut/resource evidence and the prohibition on estimating workforce. Source-cut event production stays conditional on actual source/custodian support; do not synthesize an event from a metric.
  `task.r19_extension.question_slices[3]` (`R18-D22-Q04`); `task.r19_extension.question_ids[8]` (`R18-D22-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
