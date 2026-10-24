# DEB-11: родитель и соединение рабочих результатов

Canonical title: Foreign residuals: connector cleanup and worktree tooling. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-11).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-11.aiohttp-lifecycle](../cards/DEB-11/aiohttp-lifecycle.md) | [G09](../groups/G09.md) | Application-owned aiohttp session is released on normal, exceptional and cancellation paths without closing a still-shared caller-owned session. |
| [DEB-11.fresh-worktree-toolchain](../cards/DEB-11/fresh-worktree-toolchain.md) | [G09](../groups/G09.md) | Documented fresh-checkout command uses intended editable source, lock, package links and toolchain; setup non-receipt stays distinct from product defect. |

## Реальный join

aiohttp-lifecycle emits Bounded lifecycle behavior plus existing-handler tests and originating-lane evidence.; fresh-worktree-toolchain emits Source-qualified setup receipt with explicit tooling versus product finding.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh existing Fabric handlers/tests and tools/devx/workspace setup check.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-11.aiohttp-lifecycle](../cards/DEB-11/aiohttp-lifecycle.md), [DEB-11.fresh-worktree-toolchain](../cards/DEB-11/fresh-worktree-toolchain.md).

**Fresh consumer / ответственный контур:** Fresh existing Fabric handlers/tests and tools/devx/workspace setup check.

**Review размера:** Connector resource lifecycle and fresh-worktree toolchain identity have different owners and falsifiers.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This is shared original-criteria, source-rebind, lane-disposition, or setup-boundary context for the two recovered owner results.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `solution.preferred_solution`; `solution.implementation_steps[0]`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.acceptance_discriminators[2]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`
- **binding** — This is shared original-criteria, source-rebind, lane-disposition, or setup-boundary context for the two recovered owner results.
  `task.migration`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
