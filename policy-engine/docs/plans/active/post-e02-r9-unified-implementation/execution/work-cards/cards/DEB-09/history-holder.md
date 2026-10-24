# DEB-09.history-holder — Проверить independent history holder

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Complete-history authenticity is established only by an independent holder whose admitted evidence covers the required history.

**Предпочтительное решение.** Reuse current history verification and LIF-01 intake; verify independence, content binding, coverage and relevant history.

**Граница владельца.** External holder supplies evidence; PolicyOS consumes/validates, not a history authority. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Independent holder evidence and complete required epoch/claim history.

**Выход и consumer.** Coverage-bound verified history receipt or typed incomplete-history refusal.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh protected epoch-history/current-decision consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Complete-history authenticity is established only by an independent holder whose admitted evidence covers the required history.

**Distinguishing negative.** Partial or self-held history cannot pass as complete independent history.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Complete-history authenticity is established only by an independent holder whose admitted evidence covers the required history.

**Граница контекста.** History-holder authority is a distinct slot, even where the same institution participates in another act.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-09.w5-crosswalk](../../cards/DEB-09/w5-crosswalk.md) | Consume only for the exact composition described here: Read the named output through Fresh protected epoch-history/current-decision consumer.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments require independent holder evidence covering complete history.
  `solution.free_grow.resource_behavior`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
