# CAP-02: родитель и соединение рабочих результатов

Canonical title: Safe capture, complete immutable snapshot and exact reuse. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/01-capture.md#CAP-02).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [CAP-02.transport-boundary](../cards/CAP-02/transport-boundary.md) | [G09](../groups/G09.md) | Only an authorized exact target/attempt can be reached, including redirects, DNS resolution, credentials, and controlled proxies. |
| [CAP-02.single-response-root](../cards/CAP-02/single-response-root.md) | [G01](../groups/G01.md) | A complete retained response has one immutable root; a later reader returns the same verified bytes or unavailable. |
| [CAP-02.continuation-and-frontier](../cards/CAP-02/continuation-and-frontier.md) | [G01](../groups/G01.md) | Only source-supported complete coverage and a fenced expected-head commit advance resumable progress. |
| [CAP-02.second-source-adapter](../cards/CAP-02/second-source-adapter.md) | [G01](../groups/G01.md) | A second source's actual protocol/parser has its own complete receipt and cannot borrow WDI or another route's proof. |

## Реальный join

Compose per-hop transport with selected root; continuation with LIF-03 only when activated; second-source receipt with LIF-08. Fresh reader resolves bytes and LIF-05 admits each placement. No cross-protocol/backend parity inference. Original source pins, stage/dispatch gates, conditional execution, completion planes and leases remain authoritative. dependency_routes maps consumption only. Identity/navigation/dispatch/mirrored fields in units.json.other_field_dispositions remain authoritative by parent reference.

**Outputs:** [CAP-02.transport-boundary](../cards/CAP-02/transport-boundary.md), [CAP-02.single-response-root](../cards/CAP-02/single-response-root.md), [CAP-02.continuation-and-frontier](../cards/CAP-02/continuation-and-frontier.md), [CAP-02.second-source-adapter](../cards/CAP-02/second-source-adapter.md).

**Fresh consumer / ответственный контур:** Fresh acquisition-action exact-root reader; LIF-03 expected-head consumer when continuation is selected; second-source reader/LIF-08; UI-17 projection.

**Review размера:** The preferred solution combines four independently reviewable contexts: per-hop network policy, retained representation and reader, conditional continuation/fencing, and a selected second-source adapter. R19 adds exact-content binding; it does not make these transport/protocol properties one mechanism. Refine only where source properties differ; no arbitrary quota. Mandatory companions stay with the affected property. Exact post-E02 path/lease overlap is unresolved, not presumed disjoint.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Composite task failures/removal, shared caps/ordering and multi-protocol checks reconcile transport, root, cursor and second source at parent join.
  `task.deliverable`; `task.adversarial`; `task.removal`; `task.surface`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[2]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[3]`
- **binding** — Rollback, general acceptance/companions, UI/generated navigation, writer/source limits remain parent contracts.
  `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[6]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.surface_delivery.canonical_task`; `task.surface_delivery.paths[0]`; `task.surface_delivery.paths[1]`; `task.surface_delivery.paths[2]`; `task.surface_delivery.paths[3]`; `task.surface_delivery.paths[4]`; `task.surface_delivery.paths[5]`; `task.surface_delivery.audiences`; `task.surface_delivery.negative`; `task.surface_delivery.generated_family_ref`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.migration_and_rollback`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:capture-protocol`, `resource:source/{source_profile}/fetch`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
