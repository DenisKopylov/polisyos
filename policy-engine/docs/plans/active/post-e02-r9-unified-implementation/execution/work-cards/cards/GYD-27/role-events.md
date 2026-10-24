# GYD-27.role-events — Записать real actor/tool role events

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [GYD-27](../../parents/GYD-27.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A genuine tool-loop run persists actor/action events linked to actor, run, invocation and artifacts; no-client path emits the real blocker and AgentDecisionRecord remains candidate-only.

**Предпочтительное решение.** Wire or extend the existing AgentEventBridge and canonical versioned event grammar; preserve its typed contract and status/time/provenance semantics.

**Граница владельца.** Within GYD-27's native canonical lease family write:exact-path/{canonical_repo_path}. Exact paths and overlap remain unresolved until accepted E02 lease resolution; do not presume disjointness. AgentEventBridge and canonical versioned event grammar.

**Входы.** actual tool-loop/client actor and invocation; bridge/schema and consumer

**Выход и consumer.** Persisted event package and no-client blocker

**Что можно готовить независимо.** Preparation may proceed before freeze; final execution follows the parent’s canonical stage and conditional acceptance. No new gate is introduced; resolve accepted E02 source and exact lease before writes.

**Где результат соединяется с другими.** Fresh consumer: candidate proposal reader. Event identity/replay stays with its canonical producer.

**Positive.** Real persisted event reaches candidate proposal under exact run identity.

**Distinguishing negative.** Transcript/message or missing event cannot produce a runtime role.

**Matched removal.** Remove run/event binding but retain role text; reader loses role evidence.

**Граница контекста.** Event identity/replay stays with its canonical producer.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted event-role, trusted-verifier and VOI-basis criteria are consumed separately.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `GYD-27`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Rebind bridge/schema/consumer and run the real tool loop.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`
- **binding** — Versioned role/tool grammar remains at the event owner.
  `solution.free_grow.data_or_config_growth`
- **binding** — Loop budget, candidate/refusal fallback and event identity/replay remain with actual event path.
  `solution.free_grow.resource_behavior`; `solution.migration_and_rollback`
- **execute** — Role derives from verified persisted event, not transcript.
  `solution.composition_contracts[0]`
- **execute** — Real role events reach candidate proposal consumer.
  `solution.acceptance_discriminators[0]`
- **binding** — Real tool loop/client and actor events are actual inputs.
  `solution.inputs_to_resolve[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
