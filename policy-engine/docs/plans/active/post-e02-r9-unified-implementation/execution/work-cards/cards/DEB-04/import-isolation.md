# DEB-04.import-isolation — Изолировать governed-projection imports

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-04](../../parents/DEB-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A test replacing a production module leaves no process-global fake object in either execution order.

**Предпочтительное решение.** Replace direct global sys.modules mutation with consumer injection seam or process isolation; reuse current governed-projection tests.

**Граница владельца.** Test/runtime projection owners change only the canonical test seam; subprocess is limited to demonstrated module-global state. Native exact-path lease family; paths unresolved until E02.

**Входы.** Real governed-projection producer/consumer imports and both test execution orders.

**Выход и consumer.** Deterministic test result proving production module identity is restored or case is process-isolated.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh governed-projection runtime consumer exercised through tests/unit/runtime/http/test_governed_projection_service.py.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: A test replacing a production module leaves no process-global fake object in either execution order.

**Distinguishing negative.** Run fake then real and real then fake; surviving cached aliases retaining the fake fail.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: A test replacing a production module leaves no process-global fake object in either execution order.

**Граница контекста.** A process-global import-state defect is its own falsifier and does not establish catalog, value-gate or GY-DEF22 outcomes.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-04 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments specify process-global module replacement, order leakage and the bounded import-isolation seam.
  `solution.implementation_steps[1]`; `solution.free_grow.extension_boundary`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.deviation_triggers[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
