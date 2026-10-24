# DEB-07.estimand-relations — Связать estimand strength с target semantics

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-07](../../parents/DEB-07.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Binding strength compares only owner-defined equality/derivation/transport relations over the same explicit target, regime, horizon and version.

**Предпочтительное решение.** Reuse foundry/methods/selection/requirements.py relation algebra; bind quantity-defining referents and typed incomparability.

**Граница владельца.** Foundry estimand/method owner ratifies semantic relation; no cross-target ordering by default. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Owner-ratified estimand semantics and actual target/regime/horizon propositions.

**Выход и consumer.** Versioned target-bound relation record consumed by selection/strength comparison.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh Foundry requirements/selection consumer.; composition is limited to this property and the exact original scope.

**Positive.** Owner-defined equality/derivation/transport relation сравнивает binding strength только при совпадении явных target, regime, horizon и version.

**Distinguishing negative.** Отличающийся horizon/regime либо неподдержанное cross-target отношение возвращает typed `incomparable/unknown`; численное значение само не задаёт ordering.

**Matched removal.** Отключить target/regime/horizon binding, сохранив relation label; неизменённый test, ожидающий `incomparable/unknown` для изменённого horizon, должен упасть, если consumer считает пару comparable.

**Граница контекста.** Numerical semantics are independent of CORR destination allocation and acquisition cost ownership.

## Первые действия и передача

1. Зафиксировать owner-ratified relation algebra и для выбранных quantity собрать target, regime, horizon и version referents с source identities.
2. Прогнать существующую equality/derivation/transport relation для пары с одинаковыми referents и сохранить typed result, который читает selection consumer.
3. Повторить сценарий, изменив только horizon или regime, и сохранить `incomparable/unknown` outcome.

**Ответственность и handoff.** Foundry estimand/method owner ratifies semantics; существующий requirements/selection consumer применяет relation. Межцелевое ordering не вводится по умолчанию.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-07 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-07`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind equality/derivation/transport/incomparability to explicit target, regime and horizon.
  `solution.implementation_steps[2]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[2]`; `solution.inputs_to_resolve[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
