# DEB-04.education-red-provenance — Классифицировать education-test red по slice base

Группа: [G10 — Независимые проверки и качество свидетельств](../../groups/G10.md). Родитель: [DEB-04](../../parents/DEB-04.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A carried education-importer red is inherited only when the exact command reproduces at the slice base and its complete input denominator is disjoint from changed paths.

**Предпочтительное решение.** Apply P41 from the exact slice base: replay command, inputs and output; enumerate complete input denominator and intersect with changed paths.

**Граница владельца.** Review/attribution only; does not move product ownership. Native exact-path lease family; any writes stay with the canonical owner; unresolved exact paths after E02 are not presumed disjoint.

**Входы.** Exact education slice-base commit, command, outputs, complete input denominator and current changed-path set.

**Выход и consumer.** Source-qualified inherited/owned/not_established attribution receipt; unresolved stays not_established.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Root P0-REBIND and final review consume the attribution receipt for status only; no code consumer is claimed.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: A carried education-importer red is inherited only when the exact command reproduces at the slice base and its complete input denominator is disjoint from changed paths.

**Distinguishing negative.** A nearer base, remembered failure, or zero intersection against a partial denominator cannot classify the red as inherited.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: A carried education-importer red is inherited only when the exact command reproduces at the slice base and its complete input denominator is disjoint from changed paths.

**Граница контекста.** This P41 decision is an independent conjunction, not evidence for internal catalog/discovery appointment.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-04 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-04`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments require exact slice-base replay, complete input denominator, changed-path intersection and P41 status.
  `task.acceptance_evidence_requirements[1]`; `solution.implementation_steps[0]`; `solution.migration_and_rollback`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
