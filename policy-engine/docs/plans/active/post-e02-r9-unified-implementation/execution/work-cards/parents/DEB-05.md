# DEB-05: родитель и соединение рабочих результатов

Canonical title: Native source schema and calibration contracts. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-05).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-05.retained-udf](../cards/DEB-05/retained-udf.md) | [G01](../groups/G01.md) | Malformed/unreadable retained source remains distinct from a valid empty source record. |
| [DEB-05.calibration-schema](../cards/DEB-05/calibration-schema.md) | [G03](../groups/G03.md) | Calibration version default validates under the same constrained grammar as supplied input, and the real producer emits no fixture-only fields in its strict DTO. |
| [DEB-05.fixture-authority-class](../cards/DEB-05/fixture-authority-class.md) | [G06](../groups/G06.md) | Across the complete accepted-source caller and payload-kind census, no _with_runtime_fixture_authority caller injects unsupported authority fields for any family. |

## Реальный join

retained-udf emits Typed parsed/invalid/unreadable/valid-empty result persisted with provenance and version.; calibration-schema emits Versioned calibration report accepted by same validator for default and input; strict serialized artifact.; fixture-authority-class emits Class-wide caller inventory and producer-generated persisted artifacts consumed by fresh readers; old counts 31/28 remain historical.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh retained-source reader, calibration bridge reader and every discovered helper payload-family reader.. This join does not create implementation, a second owner, or an extra start gate.

**Outputs:** [DEB-05.retained-udf](../cards/DEB-05/retained-udf.md), [DEB-05.calibration-schema](../cards/DEB-05/calibration-schema.md), [DEB-05.fixture-authority-class](../cards/DEB-05/fixture-authority-class.md).

**Fresh consumer / ответственный контур:** Fresh retained-source reader, calibration bridge reader and every discovered helper payload-family reader.

**Review размера:** Retained-source outcome, calibration DTO grammar and shared fixture-authority mutation class have distinct producers.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This is shared strict-schema, migration, input or cross-card fresh-reader requirement; parent_join reconciles retained-source, calibration and helper-family outputs.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `solution.preferred_solution`; `solution.implementation_steps[3]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[3]`; `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`
- **binding** — This is shared strict-schema, migration, input or cross-card fresh-reader requirement; parent_join reconciles retained-source, calibration and helper-family outputs.
  `task.migration`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
