# DEB-01.runner-residual — Сохранить остаток проверки runner

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DEB-01](../../parents/DEB-01.md). Роль: `verification`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Intake evidence never proves executable integrity; the existing transitive-runner falsifier detects changed transitive bytes under unchanged entry identity, or the stronger claim remains not_established.

**Предпочтительное решение.** Replay the already-covered runner/chunk falsifier on its changed surface; do not create a runner-attestation or syscall-capture service.

**Граница владельца.** Existing runner/falsifier owner only; no new authority writer. Native exact-path lease family; exact paths unresolved until E02, not presumed disjoint.

**Входы.** Accepted runner entry identity, complete transitive executable/chunk inputs and the exact original command/input denominator.

**Выход и consumer.** Bounded falsifier receipt and explicit not_established integrity residual.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Existing runner integrity consumer/falsifier; measurement intake is not accepted as its substitute.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Intake evidence never proves executable integrity; the existing transitive-runner falsifier detects changed transitive bytes under unchanged entry identity, or the stronger claim remains not_established.

**Distinguishing negative.** A self-hash, entry label or read receipt stays green if transitive-content observation is removed; the falsifier must detect that removal.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Intake evidence never proves executable integrity; the existing transitive-runner falsifier detects changed transitive bytes under unchanged entry identity, or the stronger claim remains not_established.

**Граница контекста.** This is an independent runner trust boundary; do not merge it into the FileReadMeasurement disclosure result.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-01 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments are specifically the transitive executable/chunk falsifier and its not_established integrity boundary.
  `solution.implementation_steps[3]`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
