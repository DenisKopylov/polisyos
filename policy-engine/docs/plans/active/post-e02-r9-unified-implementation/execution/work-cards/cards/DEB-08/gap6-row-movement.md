# DEB-08.gap6-row-movement — Привязать per-row re-entry к terminal movement

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-08](../../parents/DEB-08.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each GY-GAP6 row has evidence linking actual re-entry to deeper terminal movement.

**Предпочтительное решение.** Reuse runtime/quality/acquisition_route_loop.py and owner receipts; bind movement per row, not aggregate count.

**Граница владельца.** Route-loop producer owns event; GY evidence owner admits it. Native exact-path lease family; paths unresolved until E02.

**Входы.** Exact GY-GAP6 rows and source-bound re-entry/deeper terminal events.

**Выход и consumer.** Per-row movement receipt and typed GY disposition.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh GY-GAP6 evidence/register consumer.; composition is limited to this property and the exact original scope.

**Positive.** Для каждой закрываемой GY-GAP6 строки конкретный re-entry event ведёт к более глубокому terminal event той же строки; GY evidence consumer принимает отдельный receipt и disposition для каждой такой пары.

**Distinguishing negative.** Re-entry без последующего deeper terminal, terminal от соседней строки или агрегатный счётчик без row mapping оставляют строку незакрытой.

**Matched removal.** Reconciliation probe (существующий GY consumer включён): переназначить terminal event на соседний row ID, сохранив `movement achieved` marker. Проверка сопоставляет row ID обоих событий и должна показать mismatch для неизменённого утверждения о deeper-terminal movement этой строки.

**Граница контекста.** Owns the GAP6 per-row re-entry/deeper-terminal property. The mixed original step also names DS15 receipt admission; consume that separate sibling output at parent composition without taking its producer or GY register writer.

## Первые действия и передача

1. Собрать для каждого точного GY-GAP6 row ID ссылку на route-loop re-entry event и более глубокий terminal event, включая время и source receipt.
2. Пометить строки без обеих связанных записей как unresolved и передать в GY admission только per-row связи, не общий итоговый счётчик.

**Ответственность и handoff.** Route-loop producer владеет event; GY владеет evidence admission. Отдельный DS15 receipt-admission subclause остаётся за соседней карточкой.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-08 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-08.ds15-receipt-admission](../../cards/DEB-08/ds15-receipt-admission.md) | Consume only for the exact composition described here: Read the named output through Fresh GY-GAP6 evidence/register consumer.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — This mixed implementation fragment names GAP6 row movement first and then the separate DS15 receipt-admission subclause; the GAP6 card owns its per-row evidence and joins the distinct DS15 admission output without owning that producer or admission writer.
  `solution.implementation_steps[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
