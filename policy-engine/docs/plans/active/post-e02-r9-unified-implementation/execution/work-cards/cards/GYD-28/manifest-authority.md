# GYD-28.manifest-authority — Разрешить artifact authority у реального reader

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-28](../../parents/GYD-28.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Actual consumer resolves authority purpose, scope, provenance, rule version, time/currentness and boundary for the exact artifact.

**Предпочтительное решение.** Wire or extend the existing authority issuer/purpose contract and actual output consumer; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-28's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing authority issuer/purpose contract and actual output consumer.

**Входы.** artifact and canonical manifest; issuer/purpose/scope evidence; provenance, version, time and current-use rights

**Выход и consumer.** Persisted actual-consumer authority decision

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: fresh raw/public/DAG/loop output reader. One P31 intake/emission repair; resolve+content-bind+verify, no field-name authority.

**Positive.** Exact in-scope authority resolves for current use.

**Distinguishing negative.** Valid digest with absent/wrong/stale authority refuses or limits.

**Matched removal.** Remove authority bytes/binding but keep digest/manifest markers; use is blocked.

**Граница контекста.** One P31 intake/emission repair; resolve+content-bind+verify, no field-name authority.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted artifact scope and F2 criteria consumed separately by scan, CAS lifecycle and authority reader.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-28`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Resolve authority at the real consumer and enforce boundary/currentness.
  `solution.implementation_steps[2]`
- **binding** — Conforming producer registers scan scope and typed authority purpose through existing manifest grammar.
  `solution.free_grow.data_or_config_growth`
- **execute** — Valid digest without actual authority refuses/limits at reader.
  `solution.acceptance_discriminators[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
