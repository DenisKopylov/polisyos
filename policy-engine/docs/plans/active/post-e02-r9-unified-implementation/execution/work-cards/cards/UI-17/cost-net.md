# UI-17.cost-net — Развести acquisition cost и net utility

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [UI-17](../../parents/UI-17.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Cost has its own admitted schedule/ref; net utility/ranking/action only under explicit owner-approved utility contract using separate VOI/cost inputs.

**Предпочтительное решение.** Reuse existing acquisition surface and native schedule/utility owners; never subtract unknown cost.

**Граница владельца.** UI-17 projects cost/net only; schedule and utility owners stay native; shared UI-20 promotion lease if exact path overlaps.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** Owner-admitted cost schedule, DEB-13 VOI where required, approved utility contract and exact route/right inputs.

**Выход и consumer.** Separate cost/unit/basis/ref and supported net result with independent rule/time/limits.

**Что можно готовить независимо.** Prepare cost projection independently; net computation waits on exact estimand inputs.

**Где результат соединяется с другими.** Cost alone cannot authorize action; joins VOI/route only for selected composite decision.

**Positive.** Valid cost shown separately; net only with complete admissible inputs.

**Distinguishing negative.** Unknown cost is not subtracted; valid VOI does not authorize protected action.

**Matched removal.** Remove required input/utility join: hide/refuse net while preserving independent valid fields.

**Граница контекста.** VOI and cost keep distinct types/owners; no net inference from missing cost.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [UI-17.gross-voi](../../cards/UI-17/gross-voi.md) | Only for selected net-value/ENBS calculation; a standalone known cost can be displayed without numeric VOI. |
| Composition output (не start gate) [UI-17.route-eligibility](../../cards/UI-17/route-eligibility.md) | Only for selected route-specific ranking/action. Neither a gross value nor cost by itself grants permission. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `UI-17`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[1].
  `solution.composition_contracts[1]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.inputs_to_resolve[2].
  `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
