# DEB-05.retained-udf — Различать malformed и пустой retained source

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [DEB-05](../../parents/DEB-05.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Malformed/unreadable retained source remains distinct from a valid empty source record.

**Предпочтительное решение.** Reuse the actual retained-source schema/producer; make parse/read failure, malformed record and valid empty explicit outcomes.

**Граница владельца.** Retained-source producer/schema owner writes canonical source DTO. Native exact-path lease family; paths unresolved until E02.

**Входы.** Actual retained UDF payloads and supported source-schema variants.

**Выход и consumer.** Typed parsed/invalid/unreadable/valid-empty result persisted with provenance and version.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh retained-source portfolio reader.; composition is limited to this property and the exact original scope.

**Positive.** Корректная valid-empty запись сохраняется и читается как пустая; read error и malformed schema на том же пути сохраняют отдельные typed outcomes.

**Distinguishing negative.** Malformed bytes или unreadable source не превращаются в `valid_empty` и не дают portfolio consumer-у ложное пустое множество.

**Matched removal.** Отключить parse/read-error различение и fallback guard, сохранив markers; неизменённый test на том же malformed payload должен упасть, если статусы схлопываются с valid-empty.

**Граница контекста.** This is input-source validity; it does not own calibration default grammar or runtime fixture authority.

## Первые действия и передача

1. Собрать actual retained-UDF producer payloads и schema variants; сохранить отдельные примеры read error, malformed record и valid empty record.
2. Запустить каждый пример через canonical parser/producer и сравнить typed outcome плюс persisted provenance/version.
3. Прочитать созданные artifacts fresh portfolio reader-ом и сохранить, что malformed/unreadable не стали пустым portfolio.

**Ответственность и handoff.** Retained-source schema/producer owner записывает canonical DTO; fresh portfolio reader потребляет его. CAS сохранение bytes не является schema validation.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-05 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments distinguish malformed/unreadable retained source from valid empty data.
  `solution.implementation_steps[0]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
