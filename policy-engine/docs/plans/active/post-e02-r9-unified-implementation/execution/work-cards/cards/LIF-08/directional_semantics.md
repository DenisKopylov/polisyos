# LIF-08.directional_semantics — Проверить direction и requiredness

Группа: [G02 — Смысл оснований: право, метрики, ценности и участники](../../groups/G02.md). Родитель: [LIF-08](../../parents/LIF-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only mapped required facets admit; optional unknown inert, required unknown/downgrade limits affected use.

**Предпочтительное решение.** Use SourceContract/catalog and reader requiredness; schema/status is not proof.

**Граница владельца.** LIF08 binds, CAP02 captures, selected reader defines requiredness.

**Входы.** Capture binding, facet map, reader generation, consumer requiredness/unit rules.

**Выход и consumer.** Directional compatibility result at fresh reader/API.

**Что можно готовить независимо.** Consumer-specific semantics.

**Где результат соединяется с другими.** Fresh selected reader applies its requiredness and direction mapping to the bound source/profile generation; optional unknown remains inert.

**Positive.** Supported mapping passes; required unknown limited.

**Distinguishing negative.** Changed meaning/downgrade/status dispatch/source count as independence.

**Matched removal.** Remove requiredness/generation; reader fails.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:owner_readiness`: Consume selected reader/API and retirement.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-08.capture_binding](../../cards/LIF-08/capture_binding.md) | Only when a selected reader applies the mapping to an actual CAP-02 source/profile receipt and cut; a missing receipt cannot yield supported second-source output. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-08`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Requiredness and generation.
  `task.removal[0]`; `task.removal[1]`
- **execute** — Source status/API.
  `task.surface`
- **execute** — R18-D18-Q01/Q02/Q04 and IDs: meaning, direction, requiredness, generation.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`
- **execute** — SourceContract mapping, generic discovery, optional/required.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.implementation_steps[4]`
- **binding** — Versioned facet profiles.
  `solution.free_grow.data_or_config_growth`
- **binding** — Consumer requiredness, generations, claim-scoped independence.
  `solution.composition_contracts[2]`; `solution.composition_contracts[3]`; `solution.composition_contracts[4]`
- **execute** — Source status/API.
  `solution.acceptance_discriminators[3]`
- **binding** — Reader matrix.
  `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
