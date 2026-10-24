# CAP-04: родитель и соединение рабочих результатов

Canonical title: Source-specific change event producer and acquisition consumer. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/01-capture.md#CAP-04).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [CAP-04.native-events](../cards/CAP-04/native-events.md) | [G07](../groups/G07.md) | Only an authenticated, source-scoped event can state a source change with its own position and time roles. |
| [CAP-04.bounded-observation](../cards/CAP-04/bounded-observation.md) | [G07](../groups/G07.md) | Snapshot comparison supports only measured selector/profile/coverage and cannot claim source continuity between polls. |
| [CAP-04.currentness-join](../cards/CAP-04/currentness-join.md) | [G07](../groups/G07.md) | An enrolled claim is green only after replay and publication fencing cover its source dependency cut. |
| [CAP-04.operational-records](../cards/CAP-04/operational-records.md) | [G02](../groups/G02.md) | Actual custodian/adopter operational or exposure records remain source-bound measurements with their own scope/time, not a legal act, causal effect or source-change event. |
| [CAP-04.defect-impact](../cards/CAP-04/defect-impact.md) | [G10](../groups/G10.md) | A versioned defect/compromise changes only claims whose exact dependency on a pinned reproducible failure is established; an incident label alone proves no impact. |
| [CAP-04.adopter-reports](../cards/CAP-04/adopter-reports.md) | [G02](../groups/G02.md) | Complaint, adoption, harm or disagreement remains attributed testimony/operational evidence, not a legal act, causal effect, intent or resolved dispute. |

## Реальный join

Only qualified source events or bounded CAP-02 cuts reach LIF-02. Operational/exposure, pinned defect/compromise and adopter complaint/harm remain separate typed inputs, not events, legal acts, causal results or adjudications. Do not hide unresolved readers. Original source pins, stage/dispatch gates, conditional execution, completion planes and leases remain authoritative. dependency_routes maps consumption only. Identity/navigation and inherited constraints resolve from coverage.json parents[parent=CAP-04].inherited_fields and registry.json parents[id=CAP-04].inherited_dispatch_contract to the pinned task/solution rows; ignored author scratch is not a normative input.

**Outputs:** [CAP-04.native-events](../cards/CAP-04/native-events.md), [CAP-04.bounded-observation](../cards/CAP-04/bounded-observation.md), [CAP-04.operational-records](../cards/CAP-04/operational-records.md), [CAP-04.defect-impact](../cards/CAP-04/defect-impact.md), [CAP-04.adopter-reports](../cards/CAP-04/adopter-reports.md), [CAP-04.currentness-join](../cards/CAP-04/currentness-join.md).

**Fresh consumer / ответственный контур:** LIF-02 Claim Ledger/Decision Validity fresh reader/publication fence projected by UI-19. Exact operational/defect/adopter readers unresolved and consumer_missing pending E02.

**Review размера:** Source-supplied change events, measured observation cuts, and LIF-02 currentness are different evidence/authority contexts. Keeping them together risks treating a heartbeat/empty feed as a source event or giving CAP-04 a second cascade. R19 operational/incident records stay typed apart from legal events, causal assessments, and source-supplied events. Refine only where source properties differ; no arbitrary quota. Mandatory companions stay with the affected property. Exact post-E02 path/lease overlap is unresolved, not presumed disjoint.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Source-selection/fallback and task clauses join only event or bounded observation into currentness; three additional evidence classes are not promoted here.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `solution.implementation_steps[0]`; `solution.free_grow.data_or_config_growth`; `solution.inputs_to_resolve[0]`
- **binding** — Rollback, acceptance/companions, UI-17 navigation, unrun/writer/input-resolution refs remain inherited parent context.
  `task.rollback`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[6]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.surface_delivery.canonical_task`; `task.surface_delivery.paths[0]`; `task.surface_delivery.paths[1]`; `task.surface_delivery.paths[2]`; `task.surface_delivery.paths[3]`; `task.surface_delivery.paths[4]`; `task.surface_delivery.paths[5]`; `task.surface_delivery.audiences`; `task.surface_delivery.negative`; `task.surface_delivery.generated_family_ref`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:source-event-adapter/{owner}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
