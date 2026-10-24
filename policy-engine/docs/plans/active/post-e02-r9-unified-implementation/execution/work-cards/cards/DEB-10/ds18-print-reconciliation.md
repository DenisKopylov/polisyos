# DEB-10.ds18-print-reconciliation — Сверить append-only DS18 print checkpoint

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DEB-10](../../parents/DEB-10.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The second DS18 checkpoint is preserved append-only and binds exact current content, browser and print instance, only adding schema version if original cannot represent it.

**Предпочтительное решение.** Reuse existing printExport.ts flow and first C13 capture; inspect exact DS18 schema and add versioned reconciliation only if required.

**Граница владельца.** DS18 schema/print surface owner writes checkpoint; do not mutate old capture. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Original one-checkpoint schema, exact second-checkpoint requirement, current rendered content/browser/print capture and owner decision.

**Выход и consumer.** Append-only second-checkpoint record referencing first and current exact print instance, or existing-schema admission.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh runtime-dashboard print surface consumer: apps/runtime-dashboard/src/shared/export/printExport.ts.; composition is limited to this property and the exact original scope.

**Positive.** Первая DS18 checkpoint и её annotations остаются неизменными; append-only вторая запись ссылается на первую и точно связывает текущие rendered content, browser и print instance. Версия схемы добавляется лишь если исходная schema не умеет представить обе записи.

**Distinguishing negative.** Старый receipt, self-countersign или запись без текущего browser/print binding не закрывает ни inherited, ни direct C13 row.

**Matched removal.** Reconciliation probe (существующая DS18/C13 сверка остаётся включена): изменить ссылку второй checkpoint на другой browser/print instance, сохранив `reconciled` marker. Проверка должна обнаружить mismatch с текущим render и не закрыть обе C13 rows; dispositions остаются раздельными.

**Граница контекста.** This preserves the two C13 rows and existing first capture; independent accessibility report is a separate source.

## Первые действия и передача

1. Свести отдельно существующий first C13 checkpoint, требуемый second checkpoint и текущие content/browser/print instance IDs, сохранив ссылки на обе C13 closure rows.
2. Сопоставить требуемое представление с текущей DS18 schema и записать, может ли она сохранить обе контрольные точки без потери старых annotations.

**Ответственность и handoff.** Checkpoint schema и print surface принадлежат существующему DS18 owner. Внешний accessibility countersign — отдельная DEB-10 карточка.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-10 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-10`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments require append-only second DS18 checkpoint, exact browser/print instance and conditional schema evolution.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[1]`

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — DEB-10 parent two-row join: append-only DS18 second-checkpoint/current exact print instance; preserve independent accessibility evidence as a separate obligation under this selected content/carrier question. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
