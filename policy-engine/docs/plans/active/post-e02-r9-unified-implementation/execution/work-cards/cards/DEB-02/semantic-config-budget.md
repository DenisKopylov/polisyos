# DEB-02.semantic-config-budget — Считать семантическую конфигурацию

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-02](../../parents/DEB-02.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Relocating unchanged packaging settings between declared files does not reduce the semantic configuration measure; a real effective setting changes it.

**Предпочтительное решение.** Extend repository_structure_phase0.py::gate_pyproject_size to enumerate complete owner-declared packaging configuration and normalized effective settings, preserving file/key provenance.

**Граница владельца.** Existing repository-structure gate owner; no budget threshold changes without owner decision. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Owner-approved budget meaning/threshold; accepted tree and full packaging-config set including relocated Hatch settings.

**Выход и consumer.** Complete semantic-configuration inventory/measure with source file and key provenance and gate result.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh repository_structure_phase0.py::gate_pyproject_size consumer.; composition is limited to this property and the exact original scope.

**Positive.** При переносе одного и того же effective setting между файлами семантическая measure не уменьшается; добавление реальной настройки отражается в measure с указанием файла и ключа.

**Distinguishing negative.** Неизвестный формат packaging config не считается доказанным отсутствием настроек: результат остаётся неполным до решения о parser inventory, а threshold самовольно не меняется.

**Matched removal.** Отключить разбор effective keys одного объявленного config-файла, оставив file/line count и marker прежними; неизменённый relocation test должен упасть, когда перенос той же настройки уменьшает measure.

**Граница контекста.** Keep the packaging-budget predicate separate from OpenAPI export identity and reference resolution.

## Первые действия и передача

1. Составить inventory всех packaging-config файлов, включая Hatch-настройки, с нормализованными effective key/value и provenance `file → key`.
2. Сохранить relocation witness: перенести неизменённую настройку между объявленными файлами и сравнить measure; затем добавить одно действующее значение и показать изменение measure.
3. Если найден поддерживаемый packaging config вне текущего parser set, записать его формат и bounded непокрытый участок до подсчёта; сохранить owner-решение о значении существующего threshold.

**Ответственность и handoff.** Владелец существующего `gate_pyproject_size` задаёт смысл и threshold; тот же gate считает semantic settings. Карточка не вводит новый предел.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-02 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments concern effective packaging settings, relocation invariance, threshold and packaging parser scope.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[0]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
