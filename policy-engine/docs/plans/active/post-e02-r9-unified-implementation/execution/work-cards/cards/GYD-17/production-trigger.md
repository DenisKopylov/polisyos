# GYD-17.production-trigger — Один HTTP B2 запуск с CAS записью

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [GYD-17](../../parents/GYD-17.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** One authorized canonical HTTP ControlWorker→WorkspaceLoop run persists the actual graph and named records to CAS.

**Предпочтительное решение.** Wire or extend the existing Canonical production route and real CAS owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-17's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Canonical production route and real CAS owner.

**Входы.** case-binding receipt; canonical route and source-bound run identity

**Выход и consumer.** Persisted WorkspaceContract, artifact graph, SearchLedger, FrontierSnapshot and SearchExitContract

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh artifact-readback consumer. One invocation; reuse exact persisted identities for V3/V5/V7 only when cases match.

**Positive.** One real authorized trigger yields the required durable artifacts.

**Distinguishing negative.** Synthetic/helper input or a clean failed job is not production proof.

**Matched removal.** Disable durable trigger or CAS persistence while preserving run/status markers; property fails.

**Граница контекста.** One invocation; reuse exact persisted identities for V3/V5/V7 only when cases match.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [GYD-17.case-binding](../../cards/GYD-17/case-binding.md) | Consume only for the exact composition described here: Fresh consumer: fresh artifact-readback consumer. One invocation; reuse exact persisted identities for V3/V5/V7 only when cases match. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-17`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Invoke canonical HTTP route once and resolve persisted records from CAS.
  `solution.implementation_steps[1]`
- **binding** — New trigger/artifact semantics need typed authorized owner extension.
  `solution.free_grow.extension_boundary`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
