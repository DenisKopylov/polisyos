# DEB-11.aiohttp-lifecycle — Закрыть aiohttp session lifecycle

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DEB-11](../../parents/DEB-11.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Application-owned aiohttp session is released on normal, exceptional and cancellation paths without closing a still-shared caller-owned session.

**Предпочтительное решение.** After reading the already-pinned DS20 foreign criteria, repair only the existing Fabric handler/session owner and preserve caller ownership.

**Граница владельца.** Canonical existing Fabric aiohttp handler/session owner writes lifecycle fix; originating lane owns review/disposition. Native exact-path lease family; paths unresolved until E02.

**Входы.** Recovered authorized discover_data_sources/resolve_data_needs criteria and actual handler/session ownership.

**Выход и consumer.** Bounded lifecycle behavior plus existing-handler tests and originating-lane evidence.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh connector/session handler consumer and tests.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: Application-owned aiohttp session is released on normal, exceptional and cancellation paths without closing a still-shared caller-owned session.

**Distinguishing negative.** Dangling session, cancellation leak or premature close of shared caller session fails the exact ownership property.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: Application-owned aiohttp session is released on normal, exceptional and cancellation paths without closing a still-shared caller-owned session.

**Граница контекста.** This is an actual connector lifecycle property; it does not close fresh-worktree/toolchain setup.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-11 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-11`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments name existing application-owned aiohttp session release on normal/error/cancellation paths.
  `solution.implementation_steps[1]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
