# DEB-07.ds15-route-composition — Проверить DS15 route и bundle handshake

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [DEB-07](../../parents/DEB-07.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A real selected N13b route emits the existing deterministic admission artifact and its fresh consumer receipt; fixture route evidence remains test-only.

**Предпочтительное решение.** Reuse the already-built DS15 deterministic bundle producer/composition status; bind real scoped inputs and separate institutional appointments and selected-route cost.

**Граница владельца.** Existing DS15 producer and its native consumer own route/bundle. No duplicate producer or authority. Native exact-path lease family; paths unresolved until E02.

**Входы.** Actual selected N13b route, persisted DS15 artifact, accepted input scope and any genuinely required external appointments.

**Выход и consumer.** Real-route bundle receipt plus fresh consumer admission result; fixture-only status remains explicit.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh DS15/UI-17 route consumer.; composition is limited to this property and the exact original scope.

**Positive.** Реальный выбранный route с допустимым scoped input создаёт существующий deterministic admission artifact, который fresh consumer читает; fixture status остаётся test-only.

**Distinguishing negative.** Fixture-positive route и отсутствующий требуемый appointment не допускают production admission. Missing/wrong-scope cost блокирует выбранный cost-sensitive route, но не поддержанный gross result; общее имя не доказывает GYD-15 FA1.

**Matched removal.** Отключить binding actual selected route/persisted artifact к fresh consumer, сохранив route и receipt markers; неизменённый e2e test должен упасть, если real-route admission заявляется без readback artifact.

**Граница контекста.** Mechanism/receipt handshake only; separate from the DEB-08 GY register admission consumer.

## Первые действия и передача

1. Для реального selected N13b route сохранить route identity, scoped inputs, актуальные appointment outcomes и факт выбора cost-sensitive path.
2. Пропустить именно этот route через existing DS15 deterministic bundle producer; сохранить persisted artifact identity и producer receipt.
3. Прочитать receipt fresh DS15/UI-17 consumer-ом и отдельно записать, что fixture-only route test подтверждает только поведение fixture.

**Ответственность и handoff.** Существующие DS15 producer и consumer сохраняют единственный owner chain. Карточка не создаёт producer и не смешивает этот handshake с DEB-08 GY-register admission.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-07 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind the existing DS15 real route/bundle producer, selected inputs and consumer handshake.
  `solution.implementation_steps[4]`; `solution.composition_contracts[1]`; `solution.inputs_to_resolve[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
