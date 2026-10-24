# DES-11: родитель и соединение рабочих результатов

Canonical title: Evaluate adaptive policy trajectories with observable signposts and commitments. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/14-adaptive-trajectories-and-studies.md#DES-11).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DES-11.history-context](../cards/DES-11/history-context.md) | [G05](../groups/G05.md) | A trajectory’s decision-time history resolves observable event/receipt/verification/decision cutoffs, incumbent scope, actual/declared capacity, carryover, exposure and unresolved time/retention limits without future leakage. |
| [DES-11.trajectory-run](../cards/DES-11/trajectory-run.md) | [G05](../groups/G05.md) | The native temporal evaluator persists conditional policy paths for action order, observable histories, lag/carryover, incumbents, capacity and residual commitments using only information available at each decision time. |
| [DES-11.frontier-consumer](../cards/DES-11/frontier-consumer.md) | [G05](../groups/G05.md) | A fresh frontier/dossier consumer resolves the actual persisted trajectory, its exact history/method/assumptions, alternatives and limitations without conflating candidate, enacted policy or observed operation. |

## Реальный join

Reconcile actual observable-history/incumbent context through the selected evaluator into the fresh frontier/dossier. A controlled path requires actual execution; absent capacity, mandate or transitions remain conditional limits. Preserve separate act/receipt/operation clocks, old as-known results and native search/joint ownership.

**Outputs:** [DES-11.history-context](../cards/DES-11/history-context.md), [DES-11.trajectory-run](../cards/DES-11/trajectory-run.md), [DES-11.frontier-consumer](../cards/DES-11/frontier-consumer.md).

**Fresh consumer / ответственный контур:** Fresh existing Scientist frontier/dossier reader (plus authorized projection only where selected), consuming the exact trajectory path and history/cutoff context.

**Review размера:** Sequence separates actual history context, selected native temporal execution and fresh frontier consumption. DES-11 does not add an MDP, simulator, search writer or shared GYD-30 path; no hard edge is inferred from conditional R19 references.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Shared acceptance/mandatory companions apply across all three checkpoints and are reconciled at the fresh trajectory reader.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **binding** — Rollback is a parent-wide immutable-history/current-rights constraint across context, trajectory and consumer outputs.
  `task.rollback`
- **join** — The positive bundles actual A/B order, observable-history divergence and residual feasibility; root reconciles all three outputs at the fresh reader.
  `task.positive`
- **binding** — Legacy terminal-only records and rollback remain parent-wide status/migration constraints; never infer path history.
  `task.migration`
- **binding** — R16 product verification stays UNRUN until the final actual trajectory reader and evidence arrive.
  `task.r16_extension.product_verification`
- **binding** — R17 product verification remains UNRUN at the parent join.
  `task.r17_extension.product_verification`
- **binding** — R19 status, UNRUN verification and composition reference remain inherited parent contract.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Writer rule preserves DES-03/DES-04/GYD-30 and native owner boundaries for all trajectory cards.
  `task.r19_extension.writer_rule`
- **binding** — Acceptance reference is parent-wide and read against context, actual run and fresh consumer.
  `task.r19_extension.acceptance_ref`
- **binding** — Full producer/consumer/companion footprint must be resolved at parent source rebind before implementation.
  `solution.implementation_steps[0]`
- **join** — Persisted output, real consumer and authorized surface form the aggregate acceptance across all three named outputs.
  `solution.implementation_steps[2]`
- **binding** — Independent review and scoped pre-final checks are parent closeout constraints; only one final composed wave.
  `solution.implementation_steps[3]`
- **binding** — Free-grow, resource/rollback and shared owner contracts constrain the parent; no universal model/DTO or new simulator is assigned.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback[0]`; `solution.migration_and_rollback[1]`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **join** — Acceptance bundles A/B path outcomes and residual commitments; root joins actual context/run/frontier outputs at the consumer.
  `solution.acceptance_discriminators[0]`
- **binding** — Deviation triggers, external input resolution and migration remain parent-level boundaries across the three checkpoints.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:native-temporal-evaluation`, `resource:selected-method/{profile}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
