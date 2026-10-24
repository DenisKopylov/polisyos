# DES-04.acquisition-return — Связать дефицит данных с реальным возвратом

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [DES-04](../../parents/DES-04.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected evidence need reaches existing acquisition owners and an actual returned/failed/missing result changes the next acquisition choice or leaves a bounded gap-to-action record.

**Предпочтительное решение.** Bridge selected data needs to existing CAP/GYD-24 acquisition and consume DEB-13 decision value only when established. Preserve rule-bound/requirement-based acquisition without EVSI; separate compute VOI from scientific EVSI and withhold net priority/feasibility without cost/capacity inputs.

**Граница владельца.** DES-04 owns the N7 acquisition bridge under write:n7-acquisition-bridge, coordinated with its single N6 writer. CAP/GYD-24 own acquisition mechanisms and DEB-13 owns its value output; DES-08 memory is not required for first return. No scheduler, global EVSI gate or second acquisition service. Exact paths are E02-rebound.

**Входы.** An explicitly selected evidence gap/need and its decision link from existing N6/search outputs.; Actual CAP/GYD-24 acquisition result or no-hit/failed/unreturned denominator and the applicable permission/resource result; absent actual result stays absent/limited.; Cost/capacity facts only for net-value/rank/feasibility claims; gross EVSI remains conditional without them.

**Выход и consumer.** Persisted acquisition request/result/failed-arm return linked to the next choice, with source lineage, denominator, cost/capacity availability and fresh Cycle Board reader.

**Что можно готовить независимо.** Interface mapping and bounded no-hit/return cases may be prepared after E02 rebind. External query/data collection remains with authorized source/acquisition owners and is conditional on their actual permits.

**Где результат соединяется с другими.** Join actual return and gap-to-action at the existing N6/N7 next-choice reader. DES-04 changes the acquisition choice; CAP/GYD-24 retain production and DEB-13’s output is consumed only when present.

**Positive.** A permitted informative return changes a subsequent choice; a no-hit or missing outcome remains in the denominator and yields a bounded next action. An uninformative repeated query can be rejected for a stated reason.

**Distinguishing negative.** An absent result is not zero; overlapping standalone values are not summed; gross EVSI does not become net priority or feasibility without cost/capacity; permission failure cannot be hidden by a completed marker.

**Matched removal.** Retain closed-study/history markers while removing the actual result-to-next-acquisition link; the fresh next-choice test fails and omitted branches become invisible.

**Граница контекста.** This card splits the acquisition-return producer/consumer from feedback interpretation because owners, rights, and latency differ. It owns only the N7 bridge; acquisition suppliers keep their own mechanism and evidence contracts.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DES-02.hypothesis-set](../../cards/DES-02/hypothesis-set.md) | `direct:interface_agreement`: Feedback consumes actual candidate lineage; acquisition-return consumes selected evidence gaps only where this output produced them.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [DES-03](../../parents/DES-03.md) | `direct:interface_agreement`: Feedback consumes actual numerical outcomes; acquisition-return consumes a selected missing-evidence need, not all DES-03 work.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-24](../../parents/GYD-24.md) | `direct:interface_agreement`: Consumes actual acquisition producer/result through the existing interface; GYD-24 retains source/acquisition ownership.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DES-04.feedback-choice](../../cards/DES-04/feedback-choice.md) | Only for the selected same-scope composition described by this card: Join actual return and gap-to-action at the existing N6/N7 next-choice reader. DES-04 changes the acquisition choice; CAP/GYD-24 retain production and DEB-13’s output is consumed only when present. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-04`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — A declared reversible-compute profile binds eligible/selected/cost/unrun sets; it does not authorize an external study dispatch. The existing source/method/memory owner supplies its actual output; DES-04 only bridges the selected choice.
  `task.r19_extension.question_slices[1]`
- **join** — Terminal coverage binds the untried route, full denominator, profile/budget and next useful action; a cap is not exhaustive search. The existing source/method/memory owner supplies its actual output; DES-04 only bridges the selected choice.
  `task.r19_extension.question_slices[2]`
- **join** — Failed, missing and unpublished returns stay in the gap-to-action denominator; the acquisition-return reader yields a bounded claim. The existing source/method/memory owner supplies its actual output; DES-04 only bridges the selected choice.
  `task.r19_extension.question_slices[4]`
- **join** — Joint return changes the next acquisition choice; gross EVSI, net value, costs and capacity feasibility remain separate. The existing source/method/memory owner supplies its actual output; DES-04 only bridges the selected choice.
  `task.r19_extension.question_slices[5]`
- **join** — Zero-result retry and remaining branch coverage are visible; failed branches cannot count as completed acquisition. The existing source/method/memory owner supplies its actual output; DES-04 only bridges the selected choice.
  `task.r19_extension.question_slices[8]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[4]`; `task.r19_extension.question_ids[5]`; `task.r19_extension.question_ids[8]`
- **execute** — Implementation step 3 routes to acquisition-return: actual property-bound feedback/branch work stays with N6; selected CAP/GYD-24 return stays with N7; the integration witness joins both outputs.
  `solution.implementation_steps[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
