# LIF-04.trial_recovery_consumer — Сопоставить trial intent с accepted result

Группа: [G05 — Совместные расчёты, траектории и исследования](../../groups/G05.md). Родитель: [LIF-04](../../parents/LIF-04.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Fresh consumer resolves one qualified realization per native intent with honest late/duplicate dependence.

**Предпочтительное решение.** Consume DES03/GYD30 identity and LIF04 accepted outcome; no second ledger.

**Граница владельца.** LIF04 effect, DES03/GYD30 trial identity.

**Входы.** Trial intent/attempt, method guarantee, LIF04 result.

**Выход и consumer.** Fresh trial/reuse reader.

**Что можно готовить независимо.** Native trial identity and method can prepare independently; consume the actual LIF04 persisted result at the selected trial/reuse consumer.

**Где результат соединяется с другими.** Selected stochastic trial/reuse reader consumes the accepted LIF-04 result; trial identity is independent and no duty enrollment is implied.

**Positive.** Retry/late completion maps one accepted result.

**Distinguishing negative.** Seed/retry/equal scalar double-counted.

**Matched removal.** Remove intent-result binding; fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-04.effect_recovery](../../cards/LIF-04/effect_recovery.md) | Only when this selected trial intent accepts the recovered LIF-04 provider result; method identity may prepare independently and no custody-duty condition is added. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `LIF-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Stochastic intent result.
  `task.acceptance_steps[7]`
- **execute** — Native stochastic identity/result.
  `solution.composition_contracts[6]`
- **execute** — Late stochastic result.
  `solution.acceptance_discriminators[6]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
