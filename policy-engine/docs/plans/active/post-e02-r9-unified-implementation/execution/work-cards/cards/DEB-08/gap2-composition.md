# DEB-08.gap2-composition — Задать cross-scope confidence rule

Группа: [G03 — Каузальное обоснование и обучаемая модель мира](../../groups/G03.md). Родитель: [DEB-08](../../parents/DEB-08.md). Роль: `input`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** No combined confidence is emitted across scopes without an owner-approved composition rule and explicit dependence assumptions; incompatible scope remains unknown/incomparable.

**Предпочтительное решение.** Reuse confidence_ledger.py owner path; obtain product decision before composition, do not synthesize a score from unlike scopes.

**Граница владельца.** Product meaning owner decides; ledger consumer enforces. Native exact-path lease family; paths unresolved until E02.

**Входы.** Owner decision on cross-scope scope-composition and bound source scopes/dependence assumptions.

**Выход и consumer.** Versioned composition rule or typed blocked/unknown ledger result.

**Что можно готовить независимо.** Rebind source, owner, consumer and exact lease after P0-ACCEPT where applicable; any earlier census/preparation is only what the original parent stage permits. This card neither adds nor removes a start barrier.

**Где результат соединяется с другими.** Read the named output through Fresh confidence-ledger consumer.; composition is limited to this property and the exact original scope.

**Positive.** The accepted inputs produce the bounded result and the fresh consumer accepts the scoped property: No combined confidence is emitted across scopes without an owner-approved composition rule and explicit dependence assumptions; incompatible scope remains unknown/incomparable.

**Distinguishing negative.** Unknown/incomparable cross-scope inputs never yield combined value.

**Matched removal.** Remove the decisive binding for this property while retaining declarations/markers; the named consumer must fail or return its typed unknown/refusal: No combined confidence is emitted across scopes without an owner-approved composition rule and explicit dependence assumptions; incompatible scope remains unknown/incomparable.

**Граница контекста.** Decision-limited semantics; not a missing producer and not blanket GYD-31 dependency.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Consume this supplier’s actual accepted output as required by the canonical DEB-08 source dependency; this is a consumption map only and does not alter source stage/dispatch semantics.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [GYD-31](../../parents/GYD-31.md) | `interface_reference:reference_only_no_new_gate`: Conditional consumption only if the actual measured GAP2 consumer demonstrates it needs the existing ValueOuterSet output; never a blanket prerequisite or a source depends_on edge.<br>Source parent `GYD-31`: `task.deliverable`.<br>Условия: Use only as the named output/interface relationship; no new dispatch prerequisite. Canonical parent governs selected acceptance.<br>No new preparation or task-completion gate. The selected existing contract still requires its real output at the actual use described in need; absence blocks that use/claim only. An interface document is not a substituted producer receipt. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DEB-08`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — These fragments cover cross-scope composition decision and its explicit dependence assumptions.
  `solution.implementation_steps[1]`; `solution.composition_contracts[1]`; `solution.acceptance_discriminators[0]`; `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
