# CAP-01.query-disclosure — Authorize the exact outbound query

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [CAP-01](../../parents/CAP-01.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only the exact permitted query projection reaches the admitted provider and allowed logging/retention sinks.

**Предпочтительное решение.** For a selected web/LLM route, minimize and bind the exact query, purpose, sensitivity, provider/recipient and allowed logging/retention before egress through the existing source-use verifier. A verified alternative lawful basis is allowed; demonstrably owned/public non-sensitive queries need no invented custodian signature. Unknown applicable permission or sensitivity blocks the affected egress. Returned-body placement is admitted separately. Reuse SourceContract and run_acquisition_closed_loop, not a new query authority.

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
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted E02 source/caller and source denominator are consumed for rebind; preparation may precede and original P0 remains stage gate.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [CAP-01.candidate-resolution](../../cards/CAP-01/candidate-resolution.md) | When an outgoing query derives from this selected candidate; exact target/purpose/context must be bound before sending. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-01`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — Bind exact outbound projection/purpose/sensitivity/recipient/logging basis before egress; source use and returned-body placement remain distinct.
  `task.surface_delivery.audiences`; `solution.implementation_steps[2]`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[1]`
- **join** — Forged receipt/foreign purpose and bundled withheld approval, injection, log-leak/digest probes join source candidate binding with the actual egress gate.
  `task.surface_delivery.negative`; `solution.acceptance_discriminators[2]`

### Обязанности внутри составных fragments

- `solution.preferred_solution` — Pre-egress query projection is enforced by this boundary before provider/log disclosure; verified lawful alternative bases are preserved and demonstrably owned/public non-sensitive queries need no invented custodian signature. Source discovery remains candidate-resolution. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Before provider egress, authorize the exact projection/query against the selected source/provider-use contract or another verified lawful basis applicable to that exact query and provider; do not require a new custodian signature for demonstrably owned/public nonsensitive material. Unknown sensitivity or authority blocks egress or leaves the profile unclaimed. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
