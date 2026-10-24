# DEB-09.delegation-mandate — Проверить signed v2 delegation и mandate owner

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DEB-09](../../parents/DEB-09.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** DS15 delegation authority exists only when external signed v2 delegation and current mandate owner bind selected purpose and scope.

**Предпочтительное решение.** Reuse LIF-01 evidence intake and existing DS15 route; separately verify signed delegation artifact and current mandate-owner evidence.

**Граница владельца.** External delegation and mandate owner remain external acts; no local appointment or generic admin service. Native exact-path lease family; exact paths unresolved until E02.

**Входы.** Signed v2 delegation; current mandate-owner evidence; selected DS15 purpose/scope; existing LIF-01 interface.

**Выход и consumer.** Scope-bound delegation/mandate admission or typed-empty status.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh DS15 selected-route admission consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: DS15 delegation authority exists only when external signed v2 delegation and current mandate owner bind selected purpose and scope.

**Distinguishing negative.** Signature-only competence, stale mandate or wrong scope cannot authorize; GYD-15 FA1 is separate.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: DS15 delegation authority exists only when external signed v2 delegation and current mandate owner bind selected purpose and scope.

**Граница контекста.** This role is conditionally relevant to the selected DS15 route and must not become a universal start barrier.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-01](../../parents/LIF-01.md) | `direct:owner_readiness`: Consume this supplier’s actual accepted output as required by the canonical DEB-09 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DEB-09.w5-crosswalk](../../cards/DEB-09/w5-crosswalk.md) | Consume only for the exact composition described here: Read the named output through Fresh DS15 selected-route admission consumer.; composition is limited to this property and the exact original scope. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Primary accountability is DEB-09.delegation-mandate (execute) for this parent’s source-defined R19 input collection slice: DEB-09 collects external mandate separately from signer/epoch evidence. The embedded question_id R18-D23-Q02 was matched by value to the same value in task.r19_extension.question_ids; the task and preferred-solution mirrors match by question_id value. Full slice positive/adversarial/removal and mechanism refs are retained in the immutable source slice and not narrowed here.
  `task.r19_extension.question_slices[0]` (`R18-D23-Q02`); `task.r19_extension.question_ids[0]` (`R18-D23-Q02`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
