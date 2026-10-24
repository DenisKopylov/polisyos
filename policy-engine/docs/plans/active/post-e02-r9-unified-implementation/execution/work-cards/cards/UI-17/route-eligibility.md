# UI-17.route-eligibility — Связать acquisition route с правами и cutoff

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [UI-17](../../parents/UI-17.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Acquisition remains refused/limited unless exact route/cutoff/facet, rights/license, mandate and N13b evidence resolve; no auto/offline action.

**Предпочтительное решение.** Reuse DS15 route projection, CAP-03 admission and CAP-04 events; no guessed gap/new action engine.

**Граница владельца.** UI-17 owns selected route projection only; CAP/LIF supply rights/currentness; UI-20 promotion owner lease shared only if P0 finds overlap.  Parent native canonical leases: write:exact-path/{canonical_repo_path}; write:runtime-api-generated-family if changed; resource:browser/{profile} if executed. Bind exact paths and overlap at P0; unresolved paths are not presumed disjoint before E02 rebind.

**Входы.** CAP-03 purpose/right admission, CAP-04 source-change event, exact route/facet/cutoff, mandate and N13b output.

**Выход и consumer.** Fresh route/refusal with exact owner refs; unknown never authorizes or caches acquisition.

**Что можно готовить независимо.** Prepare refusal UI against agreed interface; positive waits on exact route owners.

**Где результат соединяется с другими.** Joins VOI/cost only for actions that actually consume them.

**Positive.** Lawful existing route remains; positive use follows exact owner evidence.

**Distinguishing negative.** More rows, URL/hash, unknown license/mandate, offline or guessed cutoff never authorizes.

**Matched removal.** Remove rights/currentness gate: route admission witness fails.

**Граница контекста.** This card owns route/action eligibility, not metric production.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source identity/commit and source-bound acceptance record used when rebinding this card; original parent dispatch/stage remains authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Exact purpose/right admission and selected acquisition route materialization.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-04](../../parents/CAP-04.md) | `direct:interface_agreement; acceptance:composition`: Source-qualified change/retraction/rights event for route currentness; CAP-04 does not own LIF-02.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `UI-17`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Binds route/cutoff/facet, rights, mandate and N13b input for action eligibility. Source selectors: solution.implementation_steps[0].
  `solution.implementation_steps[0]`
- **execute** — Wires permitted route/refusal through existing projection without auto/offline execution. Source selectors: solution.implementation_steps[1].
  `solution.implementation_steps[1]`
- **binding** — Binds the card's actual input/status/authority/time predicate and consumer behavior. Source selectors: solution.composition_contracts[2].
  `solution.composition_contracts[2]`
- **join** — This signal exercises the actual card property at a fresh consumer; labels/shape cannot substitute. Source selectors: solution.acceptance_discriminators[0].
  `solution.acceptance_discriminators[0]`
- **binding** — This source field contributes to route-eligibility's single observable result; its native producer/consumer boundary remains with the existing owner. Source selectors: solution.deviation_triggers[0].
  `solution.deviation_triggers[0]`
- **binding** — Records a real owner input or its conditional use; it appoints no missing producer. Source selectors: solution.inputs_to_resolve[0].
  `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
