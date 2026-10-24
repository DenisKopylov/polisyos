# GYD-28.secret-scan — Просканировать полный raw/public output set

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [GYD-28](../../parents/GYD-28.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Complete source-derived raw/public and DAG/loop outputs are enumerated and scanned for nested secret/PII at actual emission boundary.

**Предпочтительное решение.** Wire or extend the existing secret/PII scanner and canonical output owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-28's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing secret/PII scanner and canonical output owners.

**Входы.** actual raw/public and DAG/loop output set; complete file-type denominator

**Выход и consumer.** Persisted scoped scan receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: actual surface reader. Inventory is the full source set, not sample/index.

**Positive.** Every required output is scanned with source refs.

**Distinguishing negative.** Nested credential or unlisted output cannot pass by marker.

**Matched removal.** Remove real scan property while retaining manifest marker; scan fails.

**Граница контекста.** Inventory is the full source set, not sample/index.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted artifact scope and F2 criteria consumed separately by scan, CAS lifecycle and authority reader.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-28`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Enumerate complete raw/public and DAG/loop output denominator for scan; other cards consume the same set.
  `solution.implementation_steps[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
