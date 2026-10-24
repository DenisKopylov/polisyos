# GYD-20.trace-reconstruction — Офлайн восстановить сохранённую agentic trace

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [GYD-20](../../parents/GYD-20.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Persisted DAG, decisions and provenance reconstruct without live model/web call; provider/version uncertainty and redacted content stay explicit.

**Предпочтительное решение.** Wire or extend the existing orchestrator trace producer and offline reader; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-20's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing orchestrator trace producer and offline reader.

**Входы.** GYD-17 persisted V2 trace/DAG; bound output and provider/version refs

**Выход и consumer.** Offline trace reconstruction receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh trace consumer. A new live call is a distinct native invocation, not replay.

**Positive.** Stored trace resolves with known/unknown version accurately labeled.

**Distinguishing negative.** Live stochastic behavior or model consensus cannot substitute for historical reconstruction.

**Matched removal.** Remove persisted output/reference but retain marker; offline reader fails.

**Граница контекста.** A new live call is a distinct native invocation, not replay.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each card consumes its own accepted source/profile slice: operation behavior, persisted trace identity, or CAS/history rule semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../../cards/GYD-17/evidence-readback.md) | `direct:interface_agreement; acceptance:composition`: Reuse the actual V2 run’s matching deterministic input, stored DAG/provenance trace and promoted CAS refs; no identity mismatch is assumed equivalent.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-20`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — The extension distinguishes recorded LLM response reconstruction from fresh stochastic calls and deterministic numeric replay.
  `task.r14_extension.requirement`
- **join** — Bundled R19 question requires historical trace, provider version and exact invocation refs while any fresh stochastic call receives separate identity.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **execute** — Reconstruct stored DAG/provenance offline and preserve hidden/redacted content limits.
  `solution.implementation_steps[2]`
- **execute** — The slice is historical offline trace reconstruction with exact invocation and provider/version status; a fresh stochastic call is a new identity, never a replay by matching profile or alias.
  `task.r19_extension.question_slices[0]` (`R18-D11-Q01`); `task.r19_extension.question_ids[0]` (`R18-D11-Q01`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
