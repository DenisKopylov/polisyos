# DEB-05.fixture-authority-class — Закрыть класс fixture authority mutation

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-05](../../parents/DEB-05.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Across the complete accepted-source caller and payload-kind census, no _with_runtime_fixture_authority caller injects unsupported authority fields for any family.

**Предпочтительное решение.** Reuse producer-supported DTO serialization at tests/_helpers/runtime_http.py::_with_runtime_fixture_authority; enumerate every accepted-source caller and payload family, including non-calibration siblings.

**Граница владельца.** Shared test helper and actual producer serializers only; do not add fixture authority or turn generic CAS persistence into schema ownership. Native exact-path lease family; paths unresolved until E02.

**Входы.** Full current helper caller and payload-kind census plus producer-supported DTOs for each family.

**Выход и consumer.** Class-wide caller inventory and producer-generated persisted artifacts consumed by fresh readers; old counts 31/28 remain historical.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh reader tests for all discovered payload families, including test.root/test.child siblings.; composition is limited to this property and the exact original scope.

**Positive.** Для полного текущего caller/payload-kind census каждый helper вызывает producer-supported serialization, не добавляет unsupported authority fields, а fresh reader принимает соответствующий persisted artifact.

**Distinguishing negative.** Если non-calibration sibling содержит неподдерживаемое поле, strict reader отказывает; calibration-only round trip не закрывает остальные families.

**Matched removal.** Отключить helper field/serialization protection при сохранённых markers и запустить тот же non-calibration sibling test с extra authority field; неизменённый fresh-reader assertion должен упасть, если extra field сохраняется.

**Граница контекста.** One structural helper boundary closes the class; calibration-only round trip is insufficient.

## Первые действия и передача

1. Составить полный accepted-source caller census для `_with_runtime_fixture_authority` с path, payload kind и derived denominator; включить `test.root`/`test.child`, не фиксируя старые 31/28.
2. Для каждого discovered family сопоставить helper serialization с реальным producer DTO и strict schema; сохранить список полей и extras.
3. Persist producer-supported payload каждого family и прочитать fresh readers, включая non-calibration sibling; приложить outcomes.

**Ответственность и handoff.** Producer serializers владеют допустимым payload; shared test helper лишь использует их и не пишет authority. Fresh family readers проверяют схему; CAS сам по себе подтверждает только bytes.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-05 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments require complete helper caller/payload-family census and class-wide producer-supported serialization.
  `task.acceptance_evidence_requirements[0]`; `task.acceptance_evidence_requirements[1]`; `solution.implementation_steps[2]`; `solution.acceptance_discriminators[4]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
