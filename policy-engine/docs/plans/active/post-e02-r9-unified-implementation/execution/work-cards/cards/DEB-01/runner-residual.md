# DEB-01.runner-residual — Сохранить остаток проверки runner

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DEB-01](../../parents/DEB-01.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Intake evidence never proves executable integrity; the existing transitive-runner falsifier detects changed transitive bytes under unchanged entry identity, or the stronger claim remains not_established.

**Предпочтительное решение.** Replay the already-covered runner/chunk falsifier on its changed surface; do not create a runner-attestation or syscall-capture service.

**Граница владельца.** Existing runner/falsifier owner only; no new authority writer. Native exact-path lease family; exact paths unresolved until E02, not presumed disjoint.

**Входы.** Accepted runner entry identity, complete transitive executable/chunk inputs and the exact original command/input denominator.

**Выход и consumer.** Bounded falsifier receipt and explicit not_established integrity residual.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Existing runner integrity consumer/falsifier; measurement intake is not accepted as its substitute.; composition is limited to this property and the exact original scope.

**Positive.** При одинаковом entry identity изменённые байты transitive chunk обнаруживаются существующим falsifier; receipt остаётся intake-only и не заявляет integrity сверх наблюдаемого.

**Distinguishing negative.** Один entry label/hash или read receipt при неизвестном transitive closure не подтверждает целостность runner; кандидат получает `not_established`.

**Matched removal.** Отключить сравнение transitive chunk bytes, оставив entry identity, receipt и тестовые маркеры; неизменённый falsifier test с тем же изменением chunk должен упасть, потому что изменение больше не наблюдается.

**Граница контекста.** This is an independent runner trust boundary; do not merge it into the FileReadMeasurement disclosure result.

## Первые действия и передача

1. Снять baseline exact entry identity и полный список transitive executable/chunk inputs с их content identities для исходного falsifier.
2. В неизменённом original falsifier изменить байты одного transitive chunk, сохранив entry identity; записать команду, точные refs обеих версий и delta без копирования tracked bytes и наблюдённый verdict.
3. Сверить, что intake receipt сообщает только свои наблюдаемые reads; без независимо принятой runner identity записать `not_established` для executable integrity.

**Ответственность и handoff.** Существующий runner/falsifier owner запускает исходную проверку и фиксирует residual. Intake owner не становится владельцем execution integrity; сервис syscall/network capture или новый attestation путь вне этой карточки.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-01 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments are specifically the transitive executable/chunk falsifier and its not_established integrity boundary.
  `solution.implementation_steps[3]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
