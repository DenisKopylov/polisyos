# OPS-07: родитель и соединение рабочих результатов

Canonical title: Source secret resolution and provider budget accounting. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/10-operations.md#OPS-07).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [OPS-07.secret-reference](../cards/OPS-07/secret-reference.md) | [G09](../groups/G09.md) | Only a current purpose/source/recipient-scoped secret reference resolves to an ephemeral connector credential at execution; secret values never enter job payload, log, receipt or projection. |
| [OPS-07.account-budget](../cards/OPS-07/account-budget.md) | [G09](../groups/G09.md) | Concurrent attempts, retries and unknown outcomes reserve and reconcile once against the actual provider billing principal; an unknown charge remains reserved and is never treated as zero. |

## Реальный join

Compose two independent results on the same durable attempt: OPS-06 permits the source action, the secret card supplies a transient credential, and the account-budget card reserves/reconciles the actual provider principal. Fresh connector/operator readers verify absence of secret values and unknown-charge accounting.

**Outputs:** [OPS-07.secret-reference](../cards/OPS-07/secret-reference.md), [OPS-07.account-budget](../cards/OPS-07/account-budget.md).

**Fresh consumer / ответственный контур:** Existing worker connector boundary and secret-reference reader; existing budget owner/account receipt reader, with LIF-04 durable attempt.

**Review размера:** Two cards because credential custody and monetary authority have different suppliers and falsifiers. OPS-07 does not appoint a secret authority or provider billing owner; exact write paths remain unresolved until source rebind.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate acceptance, coordination, or shared constraint across secret-reference, account-budget; selectors task.deliverable, task.positive, task.adversarial, task.removal, task.surface, task.rollback, task.migration, task.acceptance_steps[0], task.acceptance_steps[1], task.acceptance_steps[2], task.acceptance_steps[3], task.acceptance_steps[4], task.mandatory_companions[0], task.mandatory_companions[1], task.mandatory_companions[2], task.mandatory_companions[3], task.mandatory_companions[4], task.rollback_precedence, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.preferred_solution, solution.implementation_steps[3], solution.free_grow.data_or_config_growth, solution.migration_and_rollback, solution.composition_contracts[0], solution.acceptance_discriminators[0], solution.input_resolution_rule are reconciled by parent_join against the named card outputs and existing consumer, not implemented as peer-owner work.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.acceptance_discriminators[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
