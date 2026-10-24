# LIF-06: родитель и соединение рабочих результатов

Canonical title: Bound lifecycle work and reserve custody/control capacity. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/03-lineage.md#LIF-06).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-06.physical_admission](../cards/LIF-06/physical_admission.md) | [G09](../groups/G09.md) | Only measured dimensions with actual enforcement hard-admit; custody/control reserve remains protected. |
| [LIF-06.allocation_lifetime](../cards/LIF-06/allocation_lifetime.md) | [G09](../groups/G09.md) | Allocation charged until actual release; nested/shared/IPC/copies cannot invent capacity. |
| [LIF-06.duty_capacity](../cards/LIF-06/duty_capacity.md) | [G07](../groups/G07.md) | Selected duty uses measured capacity and LIF04 terms/age; review/miss is not service. |
| [LIF-06.material_support_accounting](../cards/LIF-06/material_support_accounting.md) | [G02](../groups/G02.md) | Cost/check/energy/copies complete only for exact edition/duty and reconciled denominator. |

## Реальный join

Join physical_admission (measured admit/defer/refuse), allocation_lifetime (live charge through actual release), duty_capacity (selected LIF04 eligibility and conditional LIF02 reaction), and material_support_accounting (scoped denominator/partial receipt). No card creates a scheduler or allocator owner.

**Outputs:** [LIF-06.physical_admission](../cards/LIF-06/physical_admission.md), [LIF-06.allocation_lifetime](../cards/LIF-06/allocation_lifetime.md), [LIF-06.duty_capacity](../cards/LIF-06/duty_capacity.md), [LIF-06.material_support_accounting](../cards/LIF-06/material_support_accounting.md).

**Fresh consumer / ответственный контур:** Existing job/progress and LIF04 due selector; LIF02 currentness only when enrolled; existing metric reader for scoped material support.

**Review размера:** 4 outputs refine R25 duty/material. Pattern pass P01/P02/P04/P09/P13/P29/P32/P37/P38; no estimate-as-enforcement or universal meter.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate spans four outputs.
  `task.deliverable`
- **join** — Adversarial fan-in/nested/spill/provider/control cross cards.
  `task.adversarial[0]`
- **binding** — Rollback/migration and common acceptance.
  `task.rollback`; `task.migration`; `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`
- **binding** — Review/companions.
  `task.acceptance_steps[9]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **join** — R16 invocation denominator/reserve/removal/ref/status.
  `task.r16_extension.requirement`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.product_verification`
- **binding** — Refs and R18-D08-Q03 input collection.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.delivery_slices[2]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Writer/ref/preferred solution/W0 inventory.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.preferred_solution`; `solution.implementation_steps[0]`
- **join** — Saturation and duty progress.
  `solution.implementation_steps[5]`
- **join** — Migration cross owners.
  `solution.migration_and_rollback`
- **join** — Adversarial and removal across physical/allocation.
  `solution.acceptance_discriminators[2]`; `solution.acceptance_discriminators[3]`
- **binding** — Parent input rule.
  `solution.input_resolution_rule`
- **binding** — task.r19_extension.question_slices[0] crosswalks by actual value to question_ids[0]. This is explicitly scoped input collection, not a new supplier appointment; retain it as parent binding. physical_admission consumes measured profile/reserve input under its existing owner.
  `task.r19_extension.question_slices[0]` (`R18-D08-Q03`); `task.r19_extension.question_ids[0]` (`R18-D08-Q03`)

## Owners и stages

**Canonical lease namespace:** `write:resource-admission`, `resource:host/{host}/memory-disk`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
