# DEB-04.catalog-absence — Проверить отсутствие catalog на границе runtime input

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-04](../../parents/DEB-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Removing the canonical catalog from an explicit fixture produces the same typed fail-closed result as the real production loader.

**Предпочтительное решение.** Reuse the production loader with an explicit temporary catalog fixture; remove the actual canonical artifact and exercise the real boundary.

**Граница владельца.** Catalog/discovery runtime owner; no repository-layout inference. Native exact-path lease family; paths unresolved until E02.

**Входы.** Canonical catalog identity and explicit fixture populated by the actual producer.

**Выход и consumer.** Typed missing-catalog refusal from the real loader and a source-qualified test receipt.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh production catalog loader/census consumer exercised by tests/repo_quality/tools/test_layer3_gy_n13a_acquisition_census.py.; composition is limited to this property and the exact original scope.

**Positive.** Когда fixture содержит canonical catalog, реальный loader разрешает именно этот artifact и возвращает соответствующий typed result.

**Distinguishing negative.** После удаления canonical catalog тот же loader выдаёт typed missing/refusal; layout репозитория или оставшиеся markers не превращают отсутствие файла в availability или empty catalog.

**Matched removal.** Отключить resolve/check canonical catalog, оставив directory layout и markers; неизменённый loader test без artifact должен упасть, если отсутствие перестало давать typed refusal.

**Граница контекста.** This validates actual catalog input absence, independent of GY-DEF22’s owner acceptance.

## Первые действия и передача

1. Создать explicit temporary catalog fixture через реальный producer и сохранить canonical artifact identity.
2. Удалить именно этот canonical artifact из fixture, не меняя repo layout и тестовые markers; вызвать production loader и сохранить typed outcome.
3. Сопоставить present/missing input результаты на одном loader, включая source-qualified receipt отказа.

**Ответственность и handoff.** Catalog/discovery runtime producer владеет catalog; production loader его потребляет. Отсутствие определяется fixture input на runtime boundary, не формой репозитория.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-04 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments specify explicit catalog fixture deletion and real loader refusal.
  `solution.implementation_steps[2]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
