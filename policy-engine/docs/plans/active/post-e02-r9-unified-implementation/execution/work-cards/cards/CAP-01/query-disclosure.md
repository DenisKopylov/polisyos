# CAP-01.query-disclosure — Authorize the exact outbound query

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [CAP-01](../../parents/CAP-01.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only the exact permitted query projection reaches the admitted provider and allowed logging/retention sinks.

**Предпочтительное решение.** For a selected web/LLM route, construct the minimum outbound query locally, bind purpose, sensitivity, exact provider/recipient and allowed retention/logging to the native source-use verifier, and admit that exact projection before egress. Keep discovery separate from admission; unknown sensitivity or authority blocks egress and logs carry only the permitted opaque/tenant-scoped decision binding. Anchors: fabric/connectors/contracts/source_contract.py:SourceContract; runtime/quality/acquisition_planner.py:run_acquisition_closed_loop.

**Граница владельца.** CAP-01 route at transport boundary; native source/custodian verifier and LIF-05 permission owner. Parent native lease family: `write:acquisition-action`, `write:source-catalog`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Minimized query, purpose/sensitivity, provider/recipient, verified permission basis, logging/retention rules.

**Выход и consumer.** Egress or refusal plus permitted opaque audit binding; never the protected query itself.

**Что можно готовить независимо.** Candidate/source selection and actual query projection can be prepared independently.

**Где результат соединяется с другими.** Approval is required immediately before each provider/log egress; it does not authorize returned-body placement.

**Positive.** An allowed query reaches only its admitted provider/log projection.

**Distinguishing negative.** Unknown sensitivity, wrong recipient, withheld grant, or page-injected instruction sends no protected query.

**Matched removal.** Keep permitted markers but remove/alter the projection binding; controlled provider/log sink detects the forbidden payload.

**Граница контекста.** Three distinct predicates share a route but need separate contexts: candidate resolution, pre-egress query authority, and claim-scoped coverage/no-hit. The R19 coverage questions are a measurement artifact, not extra prose around discovery. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source/caller and source denominator are consumed for rebind; preparation may precede and original P0 remains stage gate.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-01.candidate-resolution](../../cards/CAP-01/candidate-resolution.md) | When an outgoing query derives from this selected candidate; exact target/purpose/context must be bound before sending. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `CAP-01`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — Bind exact outbound projection/purpose/sensitivity/recipient/logging basis before egress; source use and returned-body placement remain distinct.
  `task.surface_delivery.audiences`; `solution.implementation_steps[2]`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[1]`
- **join** — Forged receipt/foreign purpose and bundled withheld approval, injection, log-leak/digest probes join source candidate binding with the actual egress gate.
  `task.surface_delivery.negative`; `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
