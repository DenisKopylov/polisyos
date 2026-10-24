# DEB-09.epoch-qualification — Ограничить semantic epoch qualification purpose

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Signed policy and exact native relation are admitted only for intended purpose, scope and complete history.

**Предпочтительное решение.** Reuse existing semantic qualification and LIF-01 evidence machinery; require the exact relation rather than vocabulary similarity.

**Граница владельца.** Existing qualification owner verifies the external act; no new appointment service. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Signed policy, exact native relation, selected purpose/scope and complete history evidence.

**Выход и consumer.** Purpose-scoped qualification/admission result with explicit typed refusal.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh decision-validity/epoch consumer.; composition is limited to this property and the exact original scope.

**Positive.** Существующий qualification path разрешает подписанную policy и exact native relation, сверяет выбранный purpose/scope и полную требуемую историю; fresh consumer принимает только соответствующую qualification.

**Distinguishing negative.** Сходство терминов вместо exact relation, неверный purpose или неполная история дают typed refusal, даже если подпись policy валидна.

**Matched removal.** Reconciliation probe (существующий verifier остаётся включён): заменить exact native-relation reference на похожую, но иную relation, сохранив `qualified` marker и policy signature. Проверка точного relation/history binding должна обнаружить несоответствие и сохранить refusal.

**Граница контекста.** Supplemental clause use of DEB-09 U015 is the purpose-scoped qualification subclause; U015 remains primarily routed once to policy-signer. This card consumes signed policy and exact relation, while applied claims remain owned by their own fresh consumer.

## Первые действия и передача

1. Зафиксировать ID подписанной policy и точную native-relation запись с source/content refs, предназначенными purpose и scope.
2. Составить coverage списка обязательной истории для этой qualification, включая valid/known time; каждый отсутствующий relation/history item отметить отдельно.

**Ответственность и handoff.** Если policy/relation основаны на внешнем акте, сам акт даёт его учреждение; точную relation/history проверяет уже существующий внутренний qualification owner. Новое назначение не создаётся.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-09.w5-crosswalk](../../cards/DEB-09/w5-crosswalk.md) | Consume only for the exact composition described here: Read the named output through Fresh decision-validity/epoch consumer.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.



### Обязанности внутри составных fragments

- `solution.preferred_solution` — purpose-scoped semantic epoch-qualification admission of the signed policy and exact native relation (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[0]` — coverage.json#parents[parent=DEB-09].clause_uses: solution.preferred_solution subclause “purpose-scoped semantic epoch-qualification admission of the signed policy and exact native relation”; consumes the mandate separately from signer/epoch evidence. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
