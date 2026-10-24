# GYD-17.case-binding — Закрепить разрешённый реальный кейс

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [GYD-17](../../parents/GYD-17.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A permitted real case, trigger authority, production access and actual measurement/evidence owner are source-bound before invocation.

**Предпочтительное решение.** Wire or extend the existing case/access and evidence authority owners; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-17's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. Existing case/access and evidence authority owners.

**Входы.** accepted E02 criteria; authorized real case/access evidence; measurement-root owner or certified ceiling

**Выход и consumer.** Case and authorization binding

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: canonical HTTP production route. Permission and measurement owner are inputs; this card does not appoint them.

**Positive.** Real case/access and evidence owner resolve under source-bound authority.

**Distinguishing negative.** Fixture/helper input or undeclared access cannot qualify as production.

**Matched removal.** Remove case/authorization binding but keep case marker; production trigger must not proceed.

**Граница контекста.** Permission and measurement owner are inputs; this card does not appoint them.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted criterion and permitted real-case/evidence-owner input consumed before the production invocation.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [FINAL-REVIEW.independent-review](../../cards/FINAL-REVIEW/independent-review.md) | `acceptance:composition`: FINAL-REVIEW consumes the fully composed outputs at the canonical composition acceptance stage. It does not block independent preparation or add a leaf/preparation gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-17`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Select and bind the smallest permitted real case and authorization.
  `solution.implementation_steps[0]`
- **binding** — Additional cases remain under production-input/authorization contract and preserve source, audience, time and provenance.
  `solution.free_grow.data_or_config_growth`
- **binding** — Accepted source, authorized real case/access, evidence owner and source-input classification are required inputs; internal bridge gaps remain assigned work.
  `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
