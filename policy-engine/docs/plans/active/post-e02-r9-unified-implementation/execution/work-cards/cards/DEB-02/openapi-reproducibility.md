# DEB-02.openapi-reproducibility — Зафиксировать воспроизводимый OpenAPI export

Группа: [G08 — Документы, интерфейсы и понятные человеку результаты](../../groups/G08.md). Родитель: [DEB-02](../../parents/DEB-02.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Identical admitted source, lock, exporter/toolchain and declared profile yield the same full OpenAPI Description and generated client inputs across controlled environments.

**Предпочтительное решение.** Reuse export_runtime_openapi.py and generate_runtime_client.py; bind only environment dimensions that actually affect bytes and resolve every allowed referenced document.

**Граница владельца.** Existing OpenAPI exporter/client-generation owners; unsupported or unresolved refs stay explicit. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Accepted source and lock identity; exporter/tool versions; declared profile; actual environment dependencies; reference policy.

**Выход и consumer.** Full resolved OAD and client-input digest/receipt, including bounded unresolved/cycle outcome.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh runtime OpenAPI export/client generation consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Identical admitted source, lock, exporter/toolchain and declared profile yield the same full OpenAPI Description and generated client inputs across controlled environments.

**Distinguishing negative.** Digesting only the entry document, dropping an unresolved/cyclic ref, or allowing unrelated host path/clock to alter output fails the property.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Identical admitted source, lock, exporter/toolchain and declared profile yield the same full OpenAPI Description and generated client inputs across controlled environments.

**Граница контекста.** This surface/export property has separate source, environment and falsifier from the semantic packaging-config budget.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-02 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DEB-02`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — These fragments bind full OAD/reference resolution, exporter/toolchain/environment identity and generated client reproducibility.
  `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
