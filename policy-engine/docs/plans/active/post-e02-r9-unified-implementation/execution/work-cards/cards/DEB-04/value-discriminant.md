# DEB-04.value-discriminant — Сверить value-gate discriminant с producer

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-04](../../parents/DEB-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Value gate accepts only exact producer/schema discriminant bytes and rejects unresolved or malformed values.

**Предпочтительное решение.** Reconcile expected discriminant against actual artifact producer/schema and add input-removal behavioral test; repair only the evidenced side.

**Граница владельца.** Value-gate and producer/schema owners retain their canonical fields; no expected value invented. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Actual producer artifact bytes, bound DTO/schema and value-gate consumer.

**Выход и consumer.** Resolved producer-bound discriminant receipt and typed refusal for malformed/unresolved bytes.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh runtime value gate exercised by tests/unit/runtime/quality/test_value_gate.py.; composition is limited to this property and the exact original scope.

**Positive.** Value gate принимает только bytes, которые actual producer выдаёт по bound schema и которые соответствуют точному discriminant; fresh runtime test читает этот результат.

**Distinguishing negative.** Missing, malformed или не совпадающие с producer bytes отвергаются; если expected bytes не установлены, статус остаётся `not_established`, а не подменяется придуманной константой.

**Matched removal.** Отключить byte/schema discriminator comparison, сохранив marker и остальные artifact fields; неизменённый runtime test с теми же неверными bytes должен упасть, если gate их принимает.

**Граница контекста.** A schema/producer truth mismatch is separate from the catalog fixture and education-red provenance.

## Первые действия и передача

1. Снять точные bytes от actual artifact producer, schema field/path и content identity; приложить producer-owner решение о том, какие bytes являются ожидаемыми.
2. Прогнать эти bytes через существующий value gate и сохранить typed outcome; отдельно получить результаты для missing, malformed и unresolved expected bytes.
3. Для каждого варианта менять только discriminator bytes, оставляя остальной artifact и marker неизменными.

**Ответственность и handoff.** Producer/schema owner подтверждает canonical bytes; существующий value-gate consumer сравнивает их. Ни один ожидаемый discriminant не выдумывается.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-04 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind exact producer/schema bytes, value-gate refusal and its missing-input falsifier.
  `solution.implementation_steps[3]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
