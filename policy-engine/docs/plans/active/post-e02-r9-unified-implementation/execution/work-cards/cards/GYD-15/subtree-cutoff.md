# GYD-15.subtree-cutoff — Независимая граница поддерева runtime

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [GYD-15](../../parents/GYD-15.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** The actual admitted executable/root/descendant-byte set is independently reconciled to its declared cutoff before it supports a runtime claim.

**Предпочтительное решение.** Reuse the existing Foundry/runtime cutoff seam, dependency_authority and current preflight refusal; add only the owner-enforced cutoff receipt needed by the existing N8 reader.

**Граница владельца.** The assigned GYD-15 lead owns engineering trace/rebind of the existing native enforcement writer and actual independent non-producing reader, with exact canonical leases resolved before dispatch and frozen at accepted-source rebind; actual E02 acceptance remains the implementation gate. The canonical CAS reader may supply the exact content-verified, version-pinned executable/root/descendant bytes, but byte integrity does not establish the declared cutoff set or independent reconciliation. The real second source and verifier provenance must support that separate predicate or N8 stays refused. This card does not own receipt storage, toolchain identity or data rights; do not introduce a generic authority engine.

**Входы.** Declared cutoff and source refs.; Actual admitted runtime subtree and exact executable/root/descendant bytes.; Canonical CAS reader’s content-verified, version-pinned bytes as identity input only; this does not prove cutoff completeness or independence.; Independent non-producing reconciliation source and verifier provenance over the actual subtree.

**Выход и consumer.** Persisted scope-bound cutoff basis receipt consumed by N8, or the existing explicit refusal.

**Что можно готовить независимо.** Define the protected interval and actual admitted byte set.; The assigned GYD-15 lead locates/rebinds the native enforcement owner and genuine independent reader/source, resolving exact paths/leases; if no independent source exists, record that evidence gap rather than appointing a nominal verifier.; Keep actual E02 acceptance and parent dispatch/resource predicates for implementation; retain preflight refusal until a real independent receipt resolves at N8.

**Где результат соединяется с другими.** At N8, the cutoff receipt must independently reconcile the actual admitted subtree against its genuine non-producing source. Canonical CAS verification establishes which bytes were read, not whether the declared set is complete or independently sourced. This remains a distinct FA1 prerequisite; N8 also requires the other three capability receipts. A shared envelope, hash or same-writer walk cannot substitute for either witness.

**Positive.** Changing the actual subtree changes the reconciled basis and makes the stale declaration refuse at N8.

**Distinguishing negative.** A signed declared path list or equal same-writer walks cannot keep admission green after actual membership changes.

**Matched removal.** Keep cutoff/path list/signature fixed while mutating the actual subtree; independent reconciliation turns the gate red.

**Граница контекста.** G09 platform boundary. Freeze the cutoff predicate as independently_reconciled (P37); a declaration/signature checks itself, so removal mutates the actual subtree (P38). Engineering owner discovery is owned preparation; independent-source evidence remains a separate property. If no native path is found, keep absent/unallocated.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source and task-scoped source rebind are the source/version basis consumed by this card; original P0-ACCEPT and parent dispatch semantics remain authoritative.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `GYD-15`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — The subtree-cutoff card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.implementation_steps[0]`
- **execute** — The subtree-cutoff card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.composition_contracts[2]`
- **execute** — The subtree-cutoff card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.acceptance_discriminators[2]`
- **execute** — The subtree-cutoff card owns this source-specific result or constraint and consumes other owners only through the named interface; no sibling rewrites that native owner.
  `solution.inputs_to_resolve[0]`

### Обязанности внутри составных fragments

- `task.adversarial` — Actual subtree boundary/removal and scope witness must contribute its real producer/fresh-consumer discriminator to this aggregate criterion; keep unrelated siblings unchanged for its matched removal. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.removal` — Actual subtree boundary/removal and scope witness must contribute its real producer/fresh-consumer discriminator to this aggregate criterion; keep unrelated siblings unchanged for its matched removal. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
