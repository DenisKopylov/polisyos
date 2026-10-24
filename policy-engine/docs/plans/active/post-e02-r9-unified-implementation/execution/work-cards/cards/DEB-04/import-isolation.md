# DEB-04.import-isolation — Изолировать governed-projection imports

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-04](../../parents/DEB-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A test replacing a production module leaves no process-global fake object in either execution order.

**Предпочтительное решение.** Replace direct global sys.modules mutation with consumer injection seam or process isolation; reuse current governed-projection tests.

**Граница владельца.** Test/runtime projection owners change only the canonical test seam; subprocess is limited to demonstrated module-global state. Native exact-path lease family; paths unresolved until E02.

**Входы.** Real governed-projection producer/consumer imports and both test execution orders.

**Выход и consumer.** Deterministic test result proving production module identity is restored or case is process-isolated.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh governed-projection runtime consumer exercised through tests/unit/runtime/http/test_governed_projection_service.py.; composition is limited to this property and the exact original scope.

**Positive.** После fake case production import в обоих порядках возвращает реальный module object; изменение теста изолировано seam-ом либо отдельным процессом.

**Distinguishing negative.** Если cached alias сохраняет fake object после очистки `sys.modules`, второй порядок даёт неверную identity/поведение, и изоляция не считается успешной.

**Matched removal.** Отключить restoration/injection/process isolation, сохранив assertions и markers; неизменённый двухпорядковый test должен упасть, если после fake case остаётся fake module object.

**Граница контекста.** A process-global import-state defect is its own falsifier and does not establish catalog, value-gate or GY-DEF22 outcomes.

## Первые действия и передача

1. Зафиксировать точку fake `sys.modules` mutation в governed-projection test и object identities fake/real module до и после импорта.
2. Запустить оба порядка — fake→real и real→fake — и сохранить конечную module identity и результат вызова production consumer.
3. Если alias переживает восстановление mapping, записать конкретный surviving reference и подтвердить выбор injection seam или process isolation.

**Ответственность и handoff.** Test/runtime projection owner меняет только canonical test seam. Subprocess допустим при доказанном surviving alias; общий test harness и управление порядком всех тестов не добавляются.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-04 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments specify process-global module replacement, order leakage and the bounded import-isolation seam.
  `solution.implementation_steps[1]`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
