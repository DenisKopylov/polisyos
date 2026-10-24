# GYD-15.receipt-resolution — Разрешение точной owner-selected квитанции

Группа: [G07 — Долгая custody: актуальность, права и переиздание](../../groups/G07.md). Родитель: [GYD-15](../../parents/GYD-15.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The fresh reader resolves the exact owner-selected persisted receipt bytes and verifies source, content, scope, lineage, time and revocation before N8 consumes them.

**Предпочтительное решение.** Wire the existing Core CAS/Foundry writer-resolver to the native FA1/N8 receipt builder. Produce and persist the typed source-resolution receipt (or exact unavailable/refusal) bound to selected bytes/source, scope, lineage, rule/version, time and revocation; a fresh N8 reader resolves that receipt. Extend a missing native producer under its canonical lease after rebind. No second CAS, source grant issuer or parallel trust owner.

**Граница владельца.** Core CAS remains the sole byte custodian; the native Foundry/FA1 receipt producer and resolver own their typed result. Root binds their exact source paths and leases after E02. This card owns delivery of the missing native producer/bridge if needed, not merely read-only inspection and not a new store.

**Входы.** Task-lead engineering rebind identifying the existing N8 reader, canonical CAS resolver and snapshot-to-N8 transport plus their lease; path discovery grants no authority and adds no start gate.; Existing canonical Core CAS resolution of each source-bound receipt to its exact content/version-bound object or typed unavailable/refusal result.; Receipt owner/scope, rule/schema version, lineage/time and revocation refs resolved from that canonical object.; Current N8 consumer.

**Выход и consumer.** Persisted source-resolution receipt or typed unavailable/refusal with exact content/provenance/use binding, consumed and read back by a fresh N8/audit reader. A caller-supplied receipt label is insufficient.

**Что можно готовить независимо.** Trace/rebind the canonical store writer and exact reader under the existing owner boundary; retain E02 acceptance and parent dispatch predicates before implementation.; Trace persistence, lineage, replacement, expiry and revocation behavior.; Bind fresh N8 readback to the selected bytes and environment.

**Где результат соединяется с другими.** At N8, resolve the other FA1 capability receipts from their existing canonical CAS objects through the native resolver and snapshot-to-N8 transport, then return the fresh resolved/refused readback. This is a consumer path only: it does not create an upstream start edge, duplicate CAS custody, or make the resolved receipt itself prove cutoff, toolchain support or data-use rights.

**Positive.** Fresh reader resolves the exact matching owner-selected receipt with verified content and scope.

**Distinguishing negative.** Missing, self-authored, stale, replaced, wrong-scope or cross-environment receipt refuses.

**Matched removal.** Remove content binding or resolver verification while retaining ref shape; the fresh reader refuses.

**Граница контекста.** G07 ongoing custody. The task lead owns locating/rebinding this internal path; negative-only refusal remains until a real source-bound receipt is produced and consumed. No independent evaluator is added to consistency-only rebuilds unless the property requires one.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-15`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — The receipt-resolution card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.implementation_steps[1]`

### Обязанности внутри составных fragments

- `task.adversarial` — Content/owner selected resolution and persisted source receipt, including unavailable must contribute its real producer/fresh-consumer discriminator to this aggregate criterion; keep unrelated siblings unchanged for its matched removal. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.removal` — Content/owner selected resolution and persisted source receipt, including unavailable must contribute its real producer/fresh-consumer discriminator to this aggregate criterion; keep unrelated siblings unchanged for its matched removal. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
