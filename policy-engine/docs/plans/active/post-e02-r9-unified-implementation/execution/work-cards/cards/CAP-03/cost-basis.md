# CAP-03.cost-basis — Привязать фактическую стоимость получения

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [CAP-03](../../parents/CAP-03.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** For a selected cost-dependent route, CAP-03 persists and admits a cost companion bound to the dated canonical acquisition_planner schedule; the same basis is reconciled by DEB-07 and consumed by DEB-13.

**Предпочтительное решение.** Extend CAP-03 native passport/admission with its cost companion, using the existing runtime/quality/acquisition_planner.py cost-schedule owner as the sole writer. Under the principal’s 2026-09-17 option A, inspect connector/comparable-ingest evidence first and prefer measured expert_hours/calendar_days/collection_mode; otherwise emit a dated, explicitly labeled and justified owner estimate. A paid/licensed source invalidates the free-source premise and requires its actual quote and rights evidence. DEB-07 reconciles the source row; DEB-13 consumes the same schedule. No new cost engine, fixture hours, hard cap, or default institutional price request for free-data engineering.

**Граница владельца.** CAP-03 owns the native admission and persisted cost companion; the existing acquisition_planner cost-schedule owner generates the dated measured/justified estimate or source quote for its selected route. DEB-07 reconciles the source row and DEB-13 consumes the same basis. Parent lease: `write:acquisition-action`, `write:acquisition-passport`. Exact post-E02 paths/overlap remain unresolved; root binds the actual path/lease before writes, and no sibling disjointness or child lease is inferred.

**Входы.** Selected cost-dependent source route and source type; connector/comparable-ingest evidence or paid-source quote/rights; dated canonical acquisition_planner cost schedule; existing DEB-07 and DEB-13 interfaces.

**Выход и consumer.** Persisted CAP-03 admission/cost companion bound to the exact dated acquisition_planner schedule and selected source route; DEB-07 disposition and DEB-13 net-value consumer reference that same basis.

**Что можно готовить независимо.** Internally locate the canonical acquisition_planner cost-schedule owner and selected CAP-03 admission path; resolve exact path/lease at E02 before writes.; For free WDI, inspect actual connector/comparable-ingest evidence, prefer measured effort, else record a dated and justified owner estimate under 2026-09-17 option A; for paid/licensed sources require the real quote and rights evidence.; Extend the native planner/admission seam if the cost schedule or CAP-03 companion is not yet emitted; do not synthesize a parallel producer or mark the work complete from a consumer-only reference.

**Где результат соединяется с другими.** CAP-03 admission persists the exact planner schedule as its cost companion; DEB-07 reconciles its source-row disposition and DEB-13 consumes the same dated basis. Free-source engineering effort, paid-source price/rights, evidence quality, permission and net value stay distinct.

**Positive.** Selected route and DEB-13 resolve same dated artifact and source basis.

**Distinguishing negative.** Missing/stale artifact, local alternate total or detached cost leaves the branch limited.

**Matched removal.** Keep cost markers but remove planner-artifact binding; fresh CAP/DEB-13 reader cannot resolve it.

**Граница контекста.** U059/U072 require a producer as well as a consumer: CAP-03 owns the native admission/cost companion and the existing acquisition_planner owner generates its schedule. Exact post-E02 path and lease must be rebound; no new producer, cost engine or supplier is created.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted source/path rebind where used; original stage gate stays inherited.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-03`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Selected cost acceptance/composition explicitly names canonical acquisition_planner artifact, DEB-07 and DEB-13.
  `task.acceptance_evidence_requirements[0]`; `solution.composition_contracts[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
