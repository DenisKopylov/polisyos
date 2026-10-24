# GYD-15.receipt-resolution — Разрешение точной owner-selected квитанции

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [GYD-15](../../parents/GYD-15.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The fresh reader resolves the exact owner-selected persisted receipt bytes and verifies source, content, scope, lineage, time and revocation before N8 consumes them.

**Предпочтительное решение.** Extend Core CAS and existing Foundry evidence contracts/resolution seam; reuse snapshot-to-N8 transport.

**Граница владельца.** The assigned GYD-15 lead traces/rebinds the existing N8 reader and snapshot-to-N8 transport, resolving native leases before dispatch and freezing paths at accepted-source rebind; actual E02 acceptance remains the implementation gate. This FA1 capability only consumes source-bound receipt objects through the canonical Core CAS resolver/reader. The canonical CAS owner retains byte custody, object writes and content verification; this card creates no receipt store, CAS writer or alternate byte reader. It does not decide cutoff independence, platform support or production-data rights.

**Входы.** Task-lead engineering rebind identifying the existing N8 reader, canonical CAS resolver and snapshot-to-N8 transport plus their lease; path discovery grants no authority and adds no start gate.; Existing canonical Core CAS resolution of each source-bound receipt to its exact content/version-bound object or typed unavailable/refusal result.; Receipt owner/scope, rule/schema version, lineage/time and revocation refs resolved from that canonical object.; Current N8 consumer.

**Выход и consumer.** Fresh N8 readback resolving the selected canonical-CAS receipt object with exact content/version and owner/scope binding, or typed refusal; this read path writes no CAS bytes or duplicate receipt store.

**Что можно готовить независимо.** Trace/rebind the canonical store writer and exact reader under the existing owner boundary; retain E02 acceptance and parent dispatch predicates before implementation.; Trace persistence, lineage, replacement, expiry and revocation behavior.; Bind fresh N8 readback to the selected bytes and environment.

**Где результат соединяется с другими.** At N8, resolve the other FA1 capability receipts from their existing canonical CAS objects through the native resolver and snapshot-to-N8 transport, then return the fresh resolved/refused readback. This is a consumer path only: it does not create an upstream start edge, duplicate CAS custody, or make the resolved receipt itself prove cutoff, toolchain support or data-use rights.

**Positive.** Fresh reader resolves the exact matching owner-selected receipt with verified content and scope.

**Distinguishing negative.** Missing, self-authored, stale, replaced, wrong-scope or cross-environment receipt refuses.

**Matched removal.** Remove content binding or resolver verification while retaining ref shape; the fresh reader refuses.

**Граница контекста.** G07 ongoing custody. The task lead owns locating/rebinding this internal path; negative-only refusal remains until a real source-bound receipt is produced and consumed. No independent evaluator is added to consistency-only rebuilds unless the property requires one.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-15`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The receipt-resolution card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.implementation_steps[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
