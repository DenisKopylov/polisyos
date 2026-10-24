# DEB-08.ds15-receipt-admission — Принять existing DS15 receipt в GY register

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-08](../../parents/DEB-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An existing DS15 receipt is admitted by GY against the exact original row and yields a GY closure disposition without a duplicate producer.

**Предпочтительное решение.** Reuse existing DS15 persisted receipt and GY evidence/register admission path; rebind exact producer interface at accepted source.

**Граница владельца.** DS15 source owner remains producer; GY owner owns receipt admission/closure. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Existing DS15 persisted artifact and exact original GY row/criterion; source rebind must identify actual interface.

**Выход и consumer.** GY register entry referencing DS15 receipt and explicit closure/remaining disposition.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh GY receipt-admission and register consumer.; composition is limited to this property and the exact original scope.

**Positive.** Существующий persisted DS15 receipt для конкретной GY-GAP6 строки совпадает по row, run, времени, версии правила и source artifact; GY admission записывает эту ссылку и свежий GY consumer выдаёт явный disposition. Сам receipt DS15 строку не закрывает.

**Distinguishing negative.** Подлинный DS15 receipt для соседней строки, другого run или другой версии не закрывает выбранную GY строку; GY сохраняет её unresolved/remaining.

**Matched removal.** Reconciliation probe (существующий GY checker включён): переставить receipt-to-row reference на соседнюю строку, оставив `closed` marker. Сверка проверяет сам receipt и original row ID; прежнее утверждение «closure требует receipt именно этой строки» должно завершиться mismatch у свежего GY consumer.

**Граница контекста.** Admission is distinct from DS15 production and from GYD-15 FA1 authority capabilities.

## Первые действия и передача

1. Составить таблицу join: точный GY-GAP6 row ID ↔ DS15 receipt ID ↔ run/time/rule version/source artifact; незамаппленные строки явно оставить unresolved.
2. Зафиксировать, какой существующий GY register consumer читает эту связь и какое отдельное closure/remaining disposition он должен записать.

**Ответственность и handoff.** DS15 остаётся producer; GY выполняет admission и disposition. Это внутренняя consumer-связь, а не новая DS15 authority или второй producer.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-08 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments admit the existing DS15 receipt into GY’s exact row and closure path without creating a producer.
  `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
