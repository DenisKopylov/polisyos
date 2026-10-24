# UI-17.gross-voi — Показать gross VOI из owner basis

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [UI-17](../../parents/UI-17.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Numeric gross VOI appears only from producer's content-bound value/ranking ref and basis; it remains distinct and may be available while cost is unknown.

**Предпочтительное решение.** Reuse acquisition_planner and conditional DEB-13 output; client does not calculate/reinterpret VOI.

**Граница владельца.** DEB-13/native planner owns metric/estimand/value basis; UI-17 projects it.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Conditional DEB-13 metric/ranking record, basis/limits/time/rule; route context only as original claim needs.

**Выход и consumer.** Gross VOI value with distinct ref/basis/time/rule and explicit cost-unknown when relevant.

**Что можно готовить независимо.** Prepare against canonical planner contract; numeric positive waits only on DEB-13 output.

**Где результат соединяется с другими.** Can join route for an action; cost is not prerequisite for independently valid gross metric.

**Positive.** Owner-supported gross VOI is visible with its own basis even when cost unknown.

**Distinguishing negative.** Ranking-only, row count, URL/hash or unsupported metric is not numeric VOI.

**Matched removal.** Remove value/basis resolver with number marker: fresh consumer refuses.

**Граница контекста.** DEB-13 condition applies to numeric claim, not refusal-only preparation.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DEB-13.ds15-numeric-voi](../../cards/DEB-13/ds15-numeric-voi.md) | `conditional_acceptance_requirements:composition`: Conditional numeric gross VOI/ranking value and basis; refusal-only prep does not wait.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: The selected acquisition surface claims a numeric VOI |
| Composition output (не start gate) [UI-17.route-eligibility](../../cards/UI-17/route-eligibility.md) | When shown for an actual selected route, bind its exact scope; route refusal does not invent or erase a separately valid gross value. No cost prerequisite. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-17`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — This source field contributes to gross-voi's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: task.acceptance_evidence_requirements[0].
  `task.acceptance_evidence_requirements[0]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[2].
  `solution.acceptance_discriminators[2]`
- **binding** — This source field contributes to gross-voi's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[1].
  `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
