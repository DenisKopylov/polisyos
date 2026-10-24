# DEB-11.aiohttp-lifecycle — Закрыть aiohttp session lifecycle

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DEB-11](../../parents/DEB-11.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Application-owned aiohttp session is released on normal, exceptional and cancellation paths without closing a still-shared caller-owned session.

**Предпочтительное решение.** After reading the already-pinned DS20 foreign criteria, repair only the existing Fabric handler/session owner and preserve caller ownership.

**Граница владельца.** Canonical existing Fabric aiohttp handler/session owner writes lifecycle fix; originating lane owns review/disposition. Native exact-path lease family; paths unresolved until E02.

**Входы.** Recovered authorized discover_data_sources/resolve_data_needs criteria and actual handler/session ownership.

**Выход и consumer.** Bounded lifecycle behavior plus existing-handler tests and originating-lane evidence.

**Что можно готовить независимо.** После разрешённого исходным stage contract source/lease rebind выполнить первые действия ниже; до разрешённой стадии — только назначенное read-only discovery. Actual supplier outputs нужны при их потреблении, а не для всей независимой подготовки. Карточка не добавляет start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh connector/session handler consumer and tests.; composition is limited to this property and the exact original scope.

**Positive.** В двух calls, названных исходным критерием, application-owned session закрывается на normal, exception и cancellation, а shared caller-owned session остаётся открытой; пункт про отсутствие session per request включается только в пределах формулировки recovered source criterion.

**Distinguishing negative.** Зависшая application-owned session после cancel/error или преждевременное закрытие общей caller-owned session означает, что lifecycle property не соблюдён.

**Matched removal.** Mechanism-removal probe (неизменённое lifecycle assertion находится вне cleanup path): убрать close для application-owned session на cancellation, оставив cleanup declaration. Наблюдение фактического session state после того же cancellation должно показать открытую session, и независимая lifecycle assertion/test обязана FAIL; тестовый результат — witness поведения, не authority.

**Граница контекста.** This is an actual connector lifecycle property; it does not close fresh-worktree/toolchain setup.

## Первые действия и передача

1. Составить criterion-to-handler matrix для исходных Atlas paragraphs и двух разрешённых calls `discover_data_sources`/`resolve_data_needs`; перенести точную формулировку про shared session/per-request только если она относится к этим calls, без новой общей session-count нормы.
2. Свести normal return, exception и cancellation в ownership trace: кто создаёт session, кто её закрывает и остаётся ли caller-owned session shared.

**Ответственность и handoff.** Это внутренний Fabric connector lifecycle fix в каноническом owner; external institution не поставляет код. Исходная lane сохраняет review/disposition, а тестовый witness не является authority.

Порядок действий внутри назначения не добавляет dependency edges. Примеры проверок дополняют полный назначенный criterion; actual commands/paths закрепляются в [packet](../../../task-decomposition/work-packet.md) после source rebind.

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
