# DEB-10.accessibility-evidence — Принять independent accessibility evidence

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-10](../../parents/DEB-10.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Independent report supports only its exact content/carrier/sample/criteria/evaluator/time scope; sample limits remain visible.

**Предпочтительное решение.** Reuse current C13 captures and existing verification path; accept external evaluator report as content-bound evidence, not internal self-countersign.

**Граница владельца.** Independent evaluator supplies report; PolicyOS verifies/admit scoped result only. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Actual DES-06 document carrier/content, evaluator identity, versioned criteria, representative sample and declared exclusions.

**Выход и consumer.** Content-bound pass/partial/limited/contested assessment with sample and time limitations.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh accessibility/document consumer for the selected carrier.; composition is limited to this property and the exact original scope.

**Positive.** Независимый report связывает текущий DES-06 content/carrier и browser/print/document instance, указывает criteria version, evaluator, time, sample и exclusions; существующий verifier принимает только это заявленное покрытие как pass/partial/limited/contested.

**Distinguishing negative.** Старый HTML receipt для текущего DOCX/print, изменённый content или непроверенная критическая страница не подтверждают universal accessibility; sample limitation остаётся видимой.

**Matched removal.** Reconciliation probe (существующий evidence verifier остаётся включён): заменить content digest или carrier/instance reference в report, сохранив `accessibility pass` marker. Проверка должна обнаружить несовпадение выбранного текущего content и вернуть not_established.

**Граница контекста.** External assessment is separate from DS18 second-print checkpoint reconciliation and cannot claim comprehension.

## Первые действия и передача

1. Определить выбранный DES-06 carrier, точный content digest и текущий browser/print/document instance вместе с accessibility criteria version.
2. Получить у независимого evaluator report schema, выборку и exclusions, затем записать evaluator provenance/time и точную привязку каждого проверенного элемента к выбранному instance.

**Ответственность и handoff.** Фактический report и границы оценки даёт независимый evaluator. Внутренние verifier и projection принимают/показывают только его ограниченное покрытие; это не evidence comprehension и не self-countersign.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-10 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-10`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments bind independent evaluator, actual content/carrier/sample/criteria and scoped accessibility result.
  `task.r14_extension.requirement`; `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.composition_contracts[0]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`
- **execute** — Primary accountability is DEB-10.accessibility-evidence (execute) for this parent’s source-defined R19 assurance slice: Provide independent accessibility evidence for the exact selected content/carrier and current browser/print/document instance; this does not prove comprehension. The embedded question_id R18-D12-Q04 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here. Parent composition: tasks.json#tasks[id=DEB-10].r19_extension.question_ids matched by value (R18-D12-Q04); coverage.json routes that question-level two-row scope/preservation constraint to the shared DEB-10 join.
  `task.r19_extension.question_slices[0]` (`R18-D12-Q04`); `task.r19_extension.question_ids[0]` (`R18-D12-Q04`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
