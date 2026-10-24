# DEB-05.calibration-schema — Согласовать calibration version grammar

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-05](../../parents/DEB-05.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Calibration version default validates under the same constrained grammar as supplied input, and the real producer emits no fixture-only fields in its strict DTO.

**Предпочтительное решение.** Reuse foundry/calibration/report.py producer/schema; constrain version type and validate defaults and supplied values under one rule.

**Граница владельца.** Calibration/report DTO producer owns schema/version meaning; extra fields remain forbidden. Native exact-path lease family; paths unresolved until E02.

**Входы.** Accepted calibration version policy, real report producer payload and strict DTO.

**Выход и consumer.** Versioned calibration report accepted by same validator for default and input; strict serialized artifact.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh calibration reader via tests/integration/foundry_calibration/test_method_calibration_bridge.py.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Calibration version default validates under the same constrained grammar as supplied input, and the real producer emits no fixture-only fields in its strict DTO.

**Distinguishing negative.** Invalid version/default or fixture-only extra field is refused at the correct producer/reader boundary.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Calibration version default validates under the same constrained grammar as supplied input, and the real producer emits no fixture-only fields in its strict DTO.

**Граница контекста.** Keep calibration grammar distinct from the class-wide fixture helper call census.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-05 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-05`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind calibration version/default grammar, strict DTO and compatibility input.
  `solution.implementation_steps[1]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
