# LIF-01.trial_realization — Связать reuse с realization

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [LIF-01](../../parents/LIF-01.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** One method-qualified realization resolves per native intent; a fresh replicate is distinct with honest dependence.

**Предпочтительное решение.** Consume DES03/GYD30 trial identity and LIF04 recovery result; LIF01 binds use.

**Граница владельца.** DES03/GYD30 own trial identity, LIF04 effect recovery, LIF01 use.

**Входы.** Native trial/attempt, LIF04 result and method guarantee.

**Выход и consumer.** Fresh trial consumer sees accepted result/dependence.

**Что можно готовить независимо.** Trial identity, attempt and method can prepare under their native owners; actual LIF01 use and LIF04 result meet only at the selected trial consumer.

**Где результат соединяется с другими.** Joins only selected stochastic/fresh replicate.

**Positive.** Late retry resolves one accepted result; new draw gets distinct identity.

**Distinguishing negative.** Seed/equal value/retry counted independent.

**Matched removal.** Remove intent/result binding; double count/substitution fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root preserves accepted E02 stage/rebind.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-09](../../parents/LIF-09.md) | `acceptance:composition`: Actual selected output is consumed by the local composition reader; acceptance is composition-only, not a preparation prerequisite.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [LIF-01.relation_use](../../cards/LIF-01/relation_use.md) | Only when a selected native trial/realization is admitted for the same scoped LIF-01 use; the trial owner retains realization identity. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Frozen/fresh replicate and interrupted retry/late intent.
  `task.acceptance_steps[6]`; `task.acceptance_steps[7]`
- **execute** — Method guarantee, retries and late result.
  `solution.composition_contracts[4]`; `solution.composition_contracts[5]`
- **execute** — Cache-on/off draw and interruption recovery.
  `solution.acceptance_discriminators[5]`; `solution.acceptance_discriminators[6]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
