# DEB-02.openapi-reproducibility — Зафиксировать воспроизводимый OpenAPI export

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DEB-02](../../parents/DEB-02.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Identical admitted source, lock, exporter/toolchain and declared profile yield the same full OpenAPI Description and generated client inputs across controlled environments.

**Предпочтительное решение.** Reuse export_runtime_openapi.py and generate_runtime_client.py; bind only environment dimensions that actually affect bytes and resolve every allowed referenced document.

**Граница владельца.** Existing OpenAPI exporter/client-generation owners; unsupported or unresolved refs stay explicit. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Accepted source and lock identity; exporter/tool versions; declared profile; actual environment dependencies; reference policy.

**Выход и consumer.** Full resolved OAD and client-input digest/receipt, including bounded unresolved/cycle outcome.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh runtime OpenAPI export/client generation consumer.; composition is limited to this property and the exact original scope.

**Positive.** При одинаковых admitted source, lock, profile и реально значимых toolchain inputs два окружения дают один digest полного OAD со всеми refs и одинаковые generated-client inputs.

**Distinguishing negative.** Missing/unresolved reference либо цикл, который выбранный resolver не может корректно представить, оставляет export неполным с явным bounded результатом. Поддержанную рекурсивную schema нельзя отвергать лишь за наличие цикла; digest только entry document не принимается как полный snapshot.

**Matched removal.** Отключить разрешение reference closure, сохранив entry digest и markers; неизменённый тест меняет только schema разрешённого `$ref` при прежнем entry document и должен упасть из-за неверного digest полного OAD.

**Граница контекста.** This surface/export property has separate source, environment and falsifier from the semantic packaging-config budget.

## Первые действия и передача

1. Для одного export записать accepted source/lock, profile, exporter/tool versions и только те environment dimensions, которые меняют OAD bytes.
2. Собрать полное reference closure OAD, включая generated-client inputs; приложить resolved refs, digest и список missing/cyclic/unresolved refs.
3. Сравнить экспорт в двух controlled environments, затем отдельно изменить API schema/разрешённый ref и unrelated host path/clock; сохранить, какие изменения должны менять digest.

**Ответственность и handoff.** Существующие OpenAPI exporter/client-generation owners создают export и inputs; свежий generator потребляет их. Внешние refs ограничиваются принятой policy, без неограниченного crawl.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-02 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-02`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind full OAD/reference resolution, exporter/toolchain/environment identity and generated client reproducibility.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
