# GYD-20.artifact-revalidation — Разрешить CAS и раздельно проверить historic/current rules

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [GYD-20](../../parents/GYD-20.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Promoted artifact refs resolve from CAS and byte digest/size are recomputed; historical and current rule results stay separate.

**Предпочтительное решение.** Wire or extend the existing Canonical CAS resolver and historical/current rule owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-20's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Canonical CAS resolver and historical/current rule owners.

**Входы.** GYD-17 CAS artifact refs; historical/current rules and schema; semantic/effective/as-of times

**Выход и consumer.** CAS integrity and separate revalidation receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh artifact verifier. No historical result rewrite; capture time can be ignored only while semantic time remains bound.

**Positive.** Resolved bytes match digest and each rule version is validated independently.

**Distinguishing negative.** Digest alone does not prove semantic or authority validity; erased semantic time fails.

**Matched removal.** Remove semantic-time binding or CAS ref with capture marker preserved; result changes or becomes not_established.

**Граница контекста.** No historical result rewrite; capture time can be ignored only while semantic time remains bound.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Each card consumes its own accepted source/profile slice: operation behavior, persisted trace identity, or CAS/history rule semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-17.production-trigger](../../cards/GYD-17/production-trigger.md), [GYD-17.evidence-readback](../../cards/GYD-17/evidence-readback.md) | `direct:interface_agreement; acceptance:composition`: Reuse the actual V2 run’s matching deterministic input, stored DAG/provenance trace and promoted CAS refs; no identity mismatch is assumed equivalent.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Source: `task.acceptance_dependencies[0]`.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-20`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Resolve CAS bytes, validate historical/current rules and preserve capture-time vs semantic-time hash behavior.
  `solution.implementation_steps[3]`; `solution.implementation_steps[4]`
- **binding** — Historical artifacts stay immutable; semantic times, rule/schema provenance and digest-vs-authority distinctions remain explicit.
  `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **binding** — Canonicalizer loss of semantic time leaves invariance unestablished pending owner correction.
  `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
