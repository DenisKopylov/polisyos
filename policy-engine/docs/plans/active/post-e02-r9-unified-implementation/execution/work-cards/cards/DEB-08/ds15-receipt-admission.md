# DEB-08.ds15-receipt-admission — Принять existing DS15 receipt в GY register

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-08](../../parents/DEB-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** An existing DS15 receipt is admitted by GY against the exact original row and yields a GY closure disposition without a duplicate producer.

**Предпочтительное решение.** Reuse existing DS15 persisted receipt and GY evidence/register admission path; rebind exact producer interface at accepted source.

**Граница владельца.** DS15 source owner remains producer; GY owner owns receipt admission/closure. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Existing DS15 persisted artifact and exact original GY row/criterion; source rebind must identify actual interface.

**Выход и consumer.** GY register entry referencing DS15 receipt and explicit closure/remaining disposition.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh GY receipt-admission and register consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: An existing DS15 receipt is admitted by GY against the exact original row and yields a GY closure disposition without a duplicate producer.

**Distinguishing negative.** Producer receipt alone never auto-closes GY row; shared ID or GYD-15 name alone is not accepted evidence or dependency.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: An existing DS15 receipt is admitted by GY against the exact original row and yields a GY closure disposition without a duplicate producer.

**Граница контекста.** Admission is distinct from DS15 production and from GYD-15 FA1 authority capabilities.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-08 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments admit the existing DS15 receipt into GY’s exact row and closure path without creating a producer.
  `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
