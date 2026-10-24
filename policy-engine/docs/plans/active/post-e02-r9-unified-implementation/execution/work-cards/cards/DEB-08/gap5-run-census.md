# DEB-08.gap5-run-census — Пересчитать production recursive-cycle runs

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-08](../../parents/DEB-08.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** GY-GAP5 enumerates complete production recursive-cycle runs/rows; fixtures stay outside numerator and repeated views are not new cases.

**Предпочтительное решение.** Reuse runtime/quality/recursive_generation_cycle.py and existing production run owner; derive full current denominator from source/run records.

**Граница владельца.** Production run owner emits census; GY consumer records evidence. Native exact-path lease family; paths unresolved until E02.

**Входы.** Owner-provided complete production run/row denominator and separately ratified exploratory-test assumptions, if selected.

**Выход и consumer.** Recomputable production run/row census with fixture exclusion and provenance.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh GY-GAP5 evidence/register consumer.; composition is limited to this property and the exact original scope.

**Positive.** Census перечисляет все production recursive-cycle runs/rows в заявленном периоде по owner source records; fixture rows не входят в числитель, а повторные показы одного события считаются один раз. GY consumer принимает эту сверенную совокупность.

**Distinguishing negative.** Fixture run, повторный просмотр одного production event или пропуск owner-recorded run не подтверждает production population и не увеличивает число независимых случаев.

**Matched removal.** Mechanism-removal probe (неизменённая проверка denominator находится вне отключённого census filter): отключить fixture exclusion/dedup, оставив `complete production census` marker, затем предъявить fixture или повторный event. Сравнение результата с owner source denominator должно показать лишнюю строку и FAIL; сам отключённый filter не считается отказывающим.

**Граница контекста.** This is a production population property, distinct from GAP6 per-row movement and GAP3 transcript.

## Первые действия и передача

1. Сформировать перечень production recursive-cycle run IDs и row IDs из записей production owner, отдельно отметив environment и provenance каждого run.
2. Сверить полный перечень с owner-provided denominator, вывести fixture IDs отдельно и сгруппировать повторные представления одного run/event.

**Ответственность и handoff.** Production run enumerator и denominator принадлежат существующему production owner; отдельная exploratory family/assumptions нужна только если её отдельно ratify-нули.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-08 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind production recursive-cycle run/row denominator and fixture exclusion.
  `solution.implementation_steps[4]`; `solution.free_grow.resource_behavior`; `solution.acceptance_discriminators[2]`; `solution.inputs_to_resolve[1]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
