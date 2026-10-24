# GYD-33.lex-l3 — L3: привязать Lex threshold/amendment as-of

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [GYD-33](../../parents/GYD-33.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Lex threshold/amendment applies only when exact source/version and effective_from/as-of bind the claim; receipt time/latest arrival is distinct.

**Предпочтительное решение.** Wire or extend the existing Lex L3 threshold/amendment owner; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-33's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Lex L3 threshold/amendment owner.

**Входы.** Lex source bytes/version; threshold and amendment; effective_from/as-of semantics; accepted consumer contract

**Выход и consumer.** Content-bound L3 threshold/amendment receipt

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: single N4/N8/N1/N2 binding bridge. Local consumer binding only; preserve Lex write ownership and history.

**Positive.** Fresh bridge binds amendment to exact effective time.

**Distinguishing negative.** Wrong effective date, missing provenance or arrival order cannot imply current legal meaning.

**Matched removal.** Remove source/time binding but keep graph row; reader refuses or limits.

**Граница контекста.** Local consumer binding only; preserve Lex write ownership and history.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source criteria consumed by distinct L2, L3 and selected S2-emission measurements; the bridge consumes the source-card outputs.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-33`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — L3 amendments grow in its separate versioned registry; L2 edges remain Scholar-owned and are joined, not co-written.
  `solution.free_grow.data_or_config_growth`

### Обязанности внутри составных fragments

- `solution.preferred_solution` — Lex owns L3 threshold/amendment with effective_from/as-of semantics. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `solution.implementation_steps[0]` — Rebind L3 threshold/amendment artifacts, versions, denominator and semantics at Lex source owner. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — Lex owns threshold/amendment source/version and effective_from/as-of semantics; receipt time and latest arrival remain distinct. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[1]` — Lex supplies the threshold/amendment with exact effective_from/as-of so the bridge can reject latest-arrival precedence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
