# DEB-09.w5-crosswalk — Сверить полный W5 authority-slot crosswalk

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `coordination`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every original W5 route slot retains distinct meaning, owner, current status and evidence need; similar vocabulary is not equivalence.

**Предпочтительное решение.** Rebind full current W5 slot set to existing role-profile/intake/admission-bundle machinery; keep each external act non-substitutable and use no appointment service.

**Граница владельца.** DEB-09 coordinates the crosswalk; external institutions supply acts, existing internal verifier consumes them. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Complete original W5 slot inventory and actual role-specific outputs from the five slot cards; complete current status.

**Выход и consumer.** Versioned W5 row-to-role/scope/evidence crosswalk and unresolved slot list.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Existing scientist/validation/decision_validity.py and the selected DS15 admission consumer read only the role-bound evidence their actual claim/route requires; no slot intake implements the applied decision.

**Positive.** Crosswalk сохраняет каждый original W5 slot как отдельную строку со своим owner/status/evidence need; пять slot outputs разрешаются к предназначенным строкам, и свежий reconciliation consumer подтверждает покрытие полного inventory.

**Distinguishing negative.** Общий source ID, строка роли, generic signature или local default не заполняет два разных W5 slots; пропуск или подмена остаётся unresolved.

**Matched removal.** Reconciliation probe (существующая сверка полного W5 inventory остаётся включена): объединить два original slot IDs в одну crosswalk row, сохранив `complete` marker. Сравнение с исходным inventory должно показать незакрытый слот, даже если число отображённых строк не изменилось.

**Граница контекста.** The role-to-claim-scope matrix is an intake contract, not an appointment or applied authority decision. Reconcile five slot outputs here; GYD-01 S7 and GYD-15 N8 remain separate consumers and are not blanket dependencies.

## Первые действия и передача

1. Экспортировать полный original W5 slot inventory с неизменёнными source IDs, каждым slot owner, current status и требуемым evidence type.
2. Сопоставить выход каждой из пяти slot-карточек только с её original rows; пустые и неоднозначные соответствия записать как unresolved, а не объединять по похожему названию роли.

**Ответственность и handoff.** Внешние учреждения поставляют свои acts; crosswalk и существующая внутренняя verifier/intake machinery лишь сверяют их. Матрица — intake contract, не назначение и не applied authority decision.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments are shared slot-inventory/crosswalk, non-substitutability and typed-status constraints; they reconcile the five role outputs without appointing suppliers.
  `solution.implementation_steps[1]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — tasks.json#tasks[id=DEB-09].r19_extension.question_ids matched by value (R18-D23-Q02); coverage route role=execute, uid=U012 (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
