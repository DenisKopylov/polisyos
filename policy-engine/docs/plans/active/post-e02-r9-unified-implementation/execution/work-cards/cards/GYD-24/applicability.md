# GYD-24.applicability — До fetch проверить полный applicability basis

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [GYD-24](../../parents/GYD-24.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** All original 16 facets and rest.json/unpd/ukons connectors are source-bound and recomputed before any acquisition.

**Предпочтительное решение.** Wire or extend the existing Canonical applicability/facet/connector owners; preserve Rule12 zero-CENTRAL behavior and typed transport adapters.; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-24's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Canonical applicability/facet/connector owners; preserve Rule12 zero-CENTRAL behavior and typed transport adapters..

**Входы.** full facet and connector definitions; source/time/version; supported capability evidence

**Выход и consumer.** Persisted full applicability basis/missing-facet result

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual acquisition reader. Does not write external law/connector sources.

**Positive.** Complete facets/connectors are admitted before fetch.

**Distinguishing negative.** Missing facet or fake connector cannot be treated applicable.

**Matched removal.** Remove one source facet while preserving declaration; recomputation blocks acquisition.

**Граница контекста.** Does not write external law/connector sources.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source defines the complete facet/connector basis consumed before acquisition.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-24`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Rebind all facets/connectors and persist applicability with source/time/version before fetch.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **binding** — Canonical resources grow through registry; new transport semantics need typed adapter/conformance.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`
- **binding** — Complete recomputed applicability precedes fetch.
  `solution.composition_contracts[0]`
- **execute** — Recompute, then show all 16 facets and three connectors before fetch.
  `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
