# LIF-01.cache_current_use — Проверить reuse и current use

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [LIF-01](../../parents/LIF-01.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Cache reuse requires qualified basis and fresh use; rights/rule/dependency/purpose/audience changes cannot reuse stale green.

**Предпочтительное решение.** Keep LIF01 use, LIF07 lineage/cache identity and LIF05 rights; extend actual reader only.

**Граница владельца.** LIF01 semantic use, LIF07 dependency owner, LIF05 rights; exact E02 path unknown, no assumed disjointness.

**Входы.** LIF01 persisted use; LIF07 role-qualified computational/semantic dependency closure and invalidation/generation evidence only when cache-eligible reuse is selected; LIF05 current rights; source/rule generation and method guarantee; selected CAP03 library consumer/profile only when that reader participates.

**Выход и consumer.** Fresh-use decision with verifier-call accounting.

**Что можно готовить независимо.** Prepare exact reader/profile against agreed owner interfaces; cache eligibility is conditional composition, never a start gate.

**Где результат соединяется с другими.** At fresh claim/use and selected CAP03 library readers, join current LIF01 use, LIF07 closure, LIF05 rights and source/rule cuts only for the selected cache-eligible guarantee; uncached/fresh-evaluation paths remain useful without it.

**Positive.** Unchanged lawful basis reuses; changed generation appears.

**Distinguishing negative.** Cross-audience hit or cache treated as permission/currentness.

**Matched removal.** Remove live-use or computational-role check; marker-only probe fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves accepted E02 stage/rebind.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-07](../../parents/LIF-07.md) | `conditional_acceptance_requirements:composition`: Actual role-qualified computational/semantic dependency closure and invalidation/generation evidence from LIF-07, or an already accepted equivalent native owner explicitly rebound at P0; include relevant negative/membership dependencies<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: A cache-eligible assessment reuse guarantee is selected; not selected for a method requiring fresh evaluation or a deliberately uncached route |
| Composition output (не start gate) [LIF-01.relation_use](../../cards/LIF-01/relation_use.md) | For an actual cache-reuse admission, bind the already persisted LIF-01 scoped use; fresh evaluation has no cache join. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Changed purpose/audience reuse is current-use qualification.
  `task.positive[1]`
- **execute** — Selected cache-eligible verifier-call/generation probe.
  `task.acceptance_steps[4]`
- **execute** — R18-D18-Q03 predicate/rule/time/use qualification.
  `task.r19_extension.question_slices[7]`; `task.r19_extension.question_ids[7]`
- **execute** — Version cache predicate/invalidation with native owners.
  `solution.implementation_steps[4]`
- **binding** — LIF07 owns dependencies; bind selected producer-reader.
  `solution.composition_contracts[3]`
- **execute** — Cache call count/new generations.
  `solution.acceptance_discriminators[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
