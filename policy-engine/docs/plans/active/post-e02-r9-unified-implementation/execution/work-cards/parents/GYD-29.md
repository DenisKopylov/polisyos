# GYD-29: родитель и соединение рабочих результатов

Canonical title: F3 time/source and 406-row reconciliation. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/04-gy-core.md#GYD-29).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [GYD-29.candidate-census](../cards/GYD-29/candidate-census.md) | [G10](../groups/G10.md) | Every current source-derived candidate-positive row has complete file-type denominator, all eight dispositions, cited findings, frozen P37 provenance and false-exclusion review; historical 406 is not a cap. |
| [GYD-29.time-roles](../cards/GYD-29/time-roles.md) | [G07](../groups/G07.md) | Every row distinguishes act, observation, publication, receipt and knowledge/as-of time; content refs resolve and stale refs emit downgrade/repair obligation. |

## Реальный join

Root reconciles complete source census/P37/P38 dispositions with S12 time-role/ref downgrade receipt.

**Outputs:** [GYD-29.candidate-census](../cards/GYD-29/candidate-census.md), [GYD-29.time-roles](../cards/GYD-29/time-roles.md).

**Fresh consumer / ответственный контур:** Fresh time-aware consumer resolves each inventoried source reference and role before reading current disposition.

**Review размера:** Census precedes dereference. 406 is history, not a cap; no zero/count without complete source traversal or role-by-timestamp inference.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Task delivery/outcomes and common accepted-source, probe, review and companion rules remain parent closure semantics.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **binding** — R19 status, lifecycle reference and lease/writer rule remain source context.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **join** — Preferred solution bundles full current candidate census/eight dispositions/P37 false-exclusion proof with S12 reference/time-role downgrade; census and time cards own those subclauses.
  `solution.preferred_solution`
- **join** — Historical 406, P35/P36 citations, P37 frozen provenance/P38 divergence and P08 distinct roles reconcile both outputs.
  `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`
- **binding** — Current source, historic baseline, firewall/time criteria, independent review owner and accepted-input classification remain explicit parent inputs.
  `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
