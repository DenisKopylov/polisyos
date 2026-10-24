# GYD-32.reviewer-qualification — Проверить reviewer qualification по exact scope

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-32](../../parents/GYD-32.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Fresh consumer resolves method/facet owner’s expertise and required independence evidence for exact scope, or admits direct recomputation on its own evidence.

**Предпочтительное решение.** Wire or extend the existing method/facet owner qualification criteria; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-32's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing method/facet owner qualification criteria.

**Входы.** exact method/facet claim scope; owner-defined expertise/conflict criterion; resolved reviewer evidence or direct recomputation

**Выход и consumer.** Scope-bound qualification/independence receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual selected method/facet review consumer. Conditional only when review is relied on; no global roster or appointment.

**Positive.** Expertise/independence resolve for exact scope or direct evidence stands independently.

**Distinguishing negative.** Self-validation, absent owner criterion/evidence or disqualifying conflict downgrades review-only support.

**Matched removal.** Remove resolved evidence but retain signature; review-only support downgrades while direct proof remains separate.

**Граница контекста.** Conditional only when review is relied on; no global roster or appointment.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source/permit/profile criteria are consumed separately by real substrate, free-grow and conditional review-evidence work.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-32`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — S0-K14 applies only to independent-correctness claims; qualification evidence remains exact-scope, not a global roster.
  `solution.composition_contracts[3]`
- **execute** — The reviewer result is exact-scope: resolve owner-defined expertise and required independence or rely on direct recomputation; no global reviewer roster or self-validation shortcut.
  `task.r19_extension.question_slices[4]` (`R18-D18-Q03`); `task.r19_extension.question_ids[4]` (`R18-D18-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
