# LIF-08.capture_binding — Привязать CAP receipt к second source

Группа: [G01 — Поиск, получение и точная фиксация источников](../../groups/G01.md). Родитель: [LIF-08](../../parents/LIF-08.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Distinct source binds to actual CAP02 receipt, profile/parser generation and own cut.

**Предпочтительное решение.** Consume CAP02; CAP alone owns capture/parser/cursor. WDI first route insufficient.

**Граница владельца.** Parent path `write:exact-path/{canonical_repo_path}` unresolved; this consumer does not appoint producer.

**Входы.** Selected second profile, CAP02 receipt/root, activated CAP03/04, issuer cut.

**Выход и consumer.** Persisted source/cut binding for reader.

**Что можно готовить независимо.** No synthetic source.

**Где результат соединяется с другими.** Selected second-source consumer binds the actual CAP-02 receipt/profile/parser generation and its own cut; WDI-only remains producer_missing.

**Positive.** Fresh reader binds exact root/profile/cut.

**Distinguishing negative.** Backdated or incomplete receipt.

**Matched removal.** Remove receipt binding but keep labels; fail.

**Граница контекста.** One observable property; other owners remain suppliers/consumers.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Root stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-03.conditional_frontier_commit](../../cards/LIF-03/conditional_frontier_commit.md) | `direct:owner_readiness`: Consume cursor/root continuity where selected.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:owner_readiness`: Actual second-source receipt; absent remains producer_missing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [LIF-08.directional_semantics](../../cards/LIF-08/directional_semantics.md) | Only for the selected second-source profile/readers whose facet meaning, direction and requiredness are claimed; the receipt can be bound without claiming semantic admission. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `LIF-08`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Trust receipt.
  `task.removal[2]`
- **binding** — CAP02/selected source explicit in parent; consume, do not appoint supplier.
  `task.required_producer_binding.supplier_task`; `task.required_producer_binding.selection`; `task.required_producer_binding.dispatch_rule`; `task.required_producer_binding.scope`
- **execute** — Select distinct profile and actual CAP receipt/cut.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **binding** — CAP supplies receipt facts.
  `solution.composition_contracts[0]`
- **binding** — WDI-only is producer_missing; actual CAP02 source inputs.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`
- **binding** — Issuer source cut as input, no appointment.
  `solution.inputs_to_resolve[3]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
