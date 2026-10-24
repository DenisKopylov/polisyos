# LIF-07.learning_consumers — Сохранить method-valid learning

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [LIF-07](../../parents/LIF-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Confirmatory change needs method-valid correction/exposure; exploratory stays candidate.

**Предпочтительное решение.** Route through existing method/world owners; LIF07 supplies influence only.

**Граница владельца.** Method/world owner writes.

**Входы.** Method/exposure/selection receipts; fresh claim reader.

**Выход и consumer.** Method-owned correction or candidate event.

**Что можно готовить независимо.** Consumer only.

**Где результат соединяется с другими.** Only valid outcome changes standing.

**Positive.** Correction updates affected; exploratory stays low-authority.

**Distinguishing negative.** Learning label promotes without correction.

**Matched removal.** Remove correction; confirmatory gate fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-07.computational_influence](../../cards/LIF-07/computational_influence.md) | Only when the selected method-owned correction/candidate depends on this influence or selection closure; LIF-07 does not promote learning. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Confirmatory/exploratory.
  `task.positive[1]`
- **execute** — Remove correction.
  `task.removal[2]`
- **execute** — R17 valid learning/removal.
  `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`
- **execute** — Method correction, exploratory candidate.
  `solution.implementation_steps[5]`
- **execute** — Exploratory and model-world plurality.
  `solution.composition_contracts[3]`; `solution.composition_contracts[4]`
- **execute** — No correction means exploratory.
  `solution.deviation_triggers[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
