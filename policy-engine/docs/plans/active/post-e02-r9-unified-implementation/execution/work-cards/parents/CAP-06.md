# CAP-06: родитель и соединение рабочих результатов

Canonical title: Restricted/private source and remote-compute outcome binding. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/01-capture.md#CAP-06).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [CAP-06.private-input](../cards/CAP-06/private-input.md) | [G05](../groups/G05.md) | A private result is bound to actual inputs, roster/omissions, alignment, executable and allowed recipient; aggregation alone does not establish inference or independence. |
| [CAP-06.remote-effect-reconciliation](../cards/CAP-06/remote-effect-reconciliation.md) | [G09](../groups/G09.md) | Every selected remote call has one exact intent/input/executable/recipient and a verifiable completed or indeterminate effect. |
| [CAP-06.rights-and-output-sinks](../cards/CAP-06/rights-and-output-sinks.md) | [G07](../groups/G07.md) | Remote completion/encryption does not authorize storing, ingesting, transferring, or publishing an output. |
| [CAP-06.solver-call-boundary](../cards/CAP-06/solver-call-boundary.md) | [G05](../groups/G05.md) | Each selected effectful solver/map evaluation is separately bound, authorized and reconcilable; replay cannot turn an uncertain effect into a fresh observation or success. |

## Реальный join

Join only outputs required by the selected provider/input/use profile: solver-call intent precedes dispatch; remote-effect-reconciliation follows the observed outcome; rights-and-output-sinks controls actual placements. private-input roster/alignment qualification is required for private/federated evidence, not every provider call. CNT-06 qualifies inference separately; OPS-09 consumes the selected cell proof. Unknown remote effects remain indeterminate; unselected profiles create no all-of wait.

**Outputs:** [CAP-06.private-input](../cards/CAP-06/private-input.md), [CAP-06.remote-effect-reconciliation](../cards/CAP-06/remote-effect-reconciliation.md), [CAP-06.solver-call-boundary](../cards/CAP-06/solver-call-boundary.md), [CAP-06.rights-and-output-sinks](../cards/CAP-06/rights-and-output-sinks.md).

**Fresh consumer / ответственный контур:** Fresh CNT-06 inference/composition reader; solver consumer on each evaluation; OPS-09 selected deployment; LIF-04/LIF-05 readers.

**Review размера:** The card combines private/federated evidence qualification, durable remote effects/retries, and output-rights/sink enforcement. R15/R16/R17/R19 explicitly assign these to separate native owners; a single implementer otherwise holds statistical, provider, and custody contexts at once. Refine only where source properties differ; no arbitrary quota. Mandatory companions stay with the affected property. Exact post-E02 path/lease overlap is unresolved, not presumed disjoint.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Composite task/positive/removal/preferred-route criteria reconcile all four outputs at the actual fresh consumer.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.r15_extension.positive`; `task.r15_extension.removal`; `solution.preferred_solution`
- **binding** — Rollback, common acceptance/companions, references/unrun state, writer/contract/input classification remain inherited; no suppliers are appointed.
  `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.r15_extension.product_verification`; `task.r16_extension.product_verification`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
