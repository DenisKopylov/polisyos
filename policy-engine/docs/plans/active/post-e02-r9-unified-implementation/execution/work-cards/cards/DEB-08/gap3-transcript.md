# DEB-08.gap3-transcript — Получить controlled release-family transcript

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-08](../../parents/DEB-08.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Transcript evidence binds actual controlled source, release family, rule version and complete row set; fixtures never count as controlled evidence.

**Предпочтительное решение.** Use the signal owner’s controlled transcript and existing GY evidence consumer; do not create a substitute transcript producer.

**Граница владельца.** Signal owner produces transcript; GY owner admits it. Native exact-path lease family; paths unresolved until E02.

**Входы.** Controlled source, release-family identity, rule version and full row denominator from the signal owner.

**Выход и consumer.** Content-bound controlled transcript receipt and explicit GY admission status.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh GY evidence/register consumer.; composition is limited to this property and the exact original scope.

**Positive.** Transcript от signal owner разрешается к фактическому controlled source и release family, несёт нужную версию правила и покрывает весь rebound row set; существующий свежий GY register consumer принимает именно этот transcript.

**Distinguishing negative.** Fixture transcript, неверный release-family ID или пропущенная строка оставляют GY-GAP3 открытым, даже если документ помечен «complete».

**Matched removal.** Reconciliation probe (существующий GY checker включён): удалить из evidence record binding одной строки к controlled source/release family, сохранив `полный transcript` marker. Проверка сверяет весь rebound row set и должна обнаружить пропуск, оставив closure неполным.

**Граница контекста.** Producer output and GY admission remain separate steps under existing owners.

## Первые действия и передача

1. Зафиксировать у signal owner точный controlled source, release-family ID, rule version и полный набор требуемых GY-GAP3 row IDs.
2. Сопоставить каждый row ID с content-bound transcript entry и сохранить отдельный список отсутствующих строк; fixture transcript пометить как непроизводственный.

**Ответственность и handoff.** Signal owner поставляет controlled transcript, GY owner его принимает. Приёмка не создаёт заменяющего transcript producer и не превращает fixture в authority.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-08 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This fragment is the controlled GY-GAP3 source/release/rule/full-row transcript criterion.
  `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
