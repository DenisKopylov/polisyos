# DEB-02: родитель и соединение рабочих результатов

Canonical title: Build/configuration gates and reproducible OpenAPI. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-02).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-02.semantic-config-budget](../cards/DEB-02/semantic-config-budget.md) | [G10](../groups/G10.md) | Relocating unchanged packaging settings between declared files does not reduce the semantic configuration measure; a real effective setting changes it. |
| [DEB-02.openapi-reproducibility](../cards/DEB-02/openapi-reproducibility.md) | [G08](../groups/G08.md) | Identical admitted source, lock, exporter/toolchain and declared profile yield the same full OpenAPI Description and generated client inputs across controlled environments. |

## Реальный join

semantic-config-budget emits Complete semantic-configuration inventory/measure with source file and key provenance and gate result.; openapi-reproducibility emits Full resolved OAD and client-input digest/receipt, including bounded unresolved/cycle outcome.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh repository_structure_phase0.py::gate_pyproject_size plus runtime OpenAPI export/client generation consumers.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-02.semantic-config-budget](../cards/DEB-02/semantic-config-budget.md), [DEB-02.openapi-reproducibility](../cards/DEB-02/openapi-reproducibility.md).

**Fresh consumer / ответственный контур:** Fresh tests/repo_quality/tools/test_export_runtime_openapi.py and runtime client generation consume the full resolved OAD; repository_structure_phase0.py::gate_pyproject_size consumes the semantic-config measure.

**Review размера:** Semantic configuration budget and reproducible full OpenAPI export have different property, inputs, consumer and falsifier.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This fragment is a genuinely shared two-predicate acceptance, migration, or input-resolution constraint; parent_join keeps config and OAD results distinct.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `solution.preferred_solution`; `solution.free_grow.data_or_config_growth`
- **binding** — This fragment is a genuinely shared two-predicate acceptance, migration, or input-resolution constraint; parent_join keeps config and OAD results distinct.
  `task.migration`; `solution.migration_and_rollback`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
