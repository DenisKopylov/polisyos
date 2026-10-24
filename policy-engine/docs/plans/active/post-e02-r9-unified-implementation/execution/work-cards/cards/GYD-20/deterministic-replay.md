# GYD-20.deterministic-replay — Повторить deterministic operation по pinned profile

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [GYD-20](../../parents/GYD-20.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** One criterion-bearing deterministic operation replays byte-identically under matching input, parameters, seed, code/rule/schema, container and dependency profile.

**Предпочтительное решение.** Wire or extend the existing operation owner’s determinism contract; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-20's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing operation owner’s determinism contract.

**Входы.** accepted operation class and V2 persisted inputs; exact profile and dependency digests

**Выход и consumer.** Replay receipt with exact named output hashes

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh replay reader. No duplicate V2 loop or live provider call; unsupported determinism is a scoped limitation.

**Positive.** Pinned deterministic operation repeats identically.

**Distinguishing negative.** Changed input/profile/semantic time or nondeterministic dependency cannot be labelled same replay.

**Matched removal.** Remove replay binding or change semantic time while keeping capture marker; digest/receipt changes or is not_established.

**Граница контекста.** No duplicate V2 loop or live provider call; unsupported determinism is a scoped limitation.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each card consumes its own accepted source/profile slice: operation behavior, persisted trace identity, or CAS/history rule semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../../cards/GYD-17/evidence-readback.md) | `direct:interface_agreement; acceptance:composition`: Reuse the actual V2 run’s matching deterministic input, stored DAG/provenance trace and promoted CAS refs; no identity mismatch is assumed equivalent.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-20`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Owner-derived classification and one matching pinned-profile deterministic replay.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **binding** — New classes and guarantees require the operation owner’s determinism contract; trace reconstruction cannot be renamed into re-execution.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`
- **execute** — Profile/input/seed/rule/semantic-time changes are replay adversaries.
  `solution.acceptance_discriminators[1]`
- **binding** — Provider/platform/hardware nondeterminism downgrades to a scoped claim.
  `solution.deviation_triggers[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
