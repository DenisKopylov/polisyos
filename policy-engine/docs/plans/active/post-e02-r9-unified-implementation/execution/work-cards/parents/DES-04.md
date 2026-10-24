# DES-04: родитель и соединение рабочих результатов

Canonical title: Close substantive N6/N7 feedback, acquisition and alternative-retention loop. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/13-productive-design.md#DES-04).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DES-04.feedback-choice](../cards/DES-04/feedback-choice.md) | [G04](../groups/G04.md) | A permitted, property-bound counterexample, actual outcome or method warning changes a later candidate/branch choice, or yields an honest limited next action with rejected, unexecuted and truncated branches visible. |
| [DES-04.acquisition-return](../cards/DES-04/acquisition-return.md) | [G01](../groups/G01.md) | A selected evidence need reaches existing acquisition owners and an actual returned/failed/missing result changes the next acquisition choice or leaves a bounded gap-to-action record. |

## Реальный join

Reconcile a property-bound feedback event and a selected acquisition return at the real next-choice consumer. A first within-run feedback result may stand without DES-08 memory; acquisition results, failure denominators and conditional costs are joined only when their actual suppliers return them.

**Outputs:** [DES-04.feedback-choice](../cards/DES-04/feedback-choice.md), [DES-04.acquisition-return](../cards/DES-04/acquisition-return.md).

**Fresh consumer / ответственный контур:** Existing N6/Cycle Board next-choice reader, consuming DES-04 feedback output and, when selected, the actual CAP/GYD-24 return via the DES-04 N7 bridge.

**Review размера:** Split R25 DES-04 along distinct N6 feedback and N7 acquisition-return producers/rights/latency. One DES-04 N6 bridge writer remains; CAP/GYD-24/DEB-13 keep their mechanisms. No EVSI requirement, scheduler or cycle is added.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Shared parent acceptance/mandatory companions are checked against both named bridge outputs and the actual N6 next-choice consumer.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **join** — Positive bundles a changed candidate, changed acquisition choice and useful budget-exhausted next action; root reconciles both cards at the fresh N6 consumer.
  `task.positive`
- **join** — This bundled removal clause independently removes feedback and acquisition-return bridges; root checks each card output against the same actual next-choice consumer.
  `task.removal`
- **join** — Cycle Board/frontier surface joins the two outputs but keeps the existing public projection boundary; no surface implementation is hidden at @parent.
  `task.surface`
- **binding** — Rollback, migration and external-input conditions span both bridge properties; source permission/budget stays with its existing owner.
  `task.rollback`; `task.migration`; `task.genuine_external_inputs[0]`
- **join** — R16 removal bundles dispatch and study-return paths; parent verifies each against actual feedback/acquisition outputs rather than a completion marker.
  `task.r16_extension.removal`
- **binding** — R16 product verification is UNRUN and belongs to the parent acceptance disposition.
  `task.r16_extension.product_verification`
- **join** — R17 removal is an aggregate next-action/consumer check across feedback and acquisition outputs.
  `task.r17_extension.removal`
- **binding** — R17 product verification remains UNRUN at parent level.
  `task.r17_extension.product_verification`
- **binding** — R19 status, runtime verification and composition ref are inherited parent contract, not leaf proof.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — The writer rule applies across both cards; DES-04 stays one N6/N7 bridge writer and suppliers are consumers, not sibling writers.
  `task.r19_extension.writer_rule`
- **binding** — Acceptance reference applies to the full parent and its two outputs.
  `task.r19_extension.acceptance_ref`
- **join** — Implementation step 4 routes to @parent: actual property-bound feedback/branch work stays with N6; selected CAP/GYD-24 return stays with N7; the integration witness joins both outputs.
  `solution.implementation_steps[4]`
- **binding** — Free-grow, resource/rights, migration and rollback conditions are shared parent-wide constraints; existing owners retain their mechanisms.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback[0]`; `solution.migration_and_rollback[1]`
- **binding** — The composition contract preserves DES-04 as one bridge writer and CAP/GYD-24/DEB-13 as mechanism owners across both cards.
  `solution.composition_contracts[0]`
- **binding** — DES-08 may prepare memory interface independently; memory is not a prerequisite for the first within-run feedback loop.
  `solution.composition_contracts[1]`
- **join** — Removing either native bridge is an aggregate integration falsifier; check the named N6 and N7 outputs separately at the fresh consumer.
  `solution.acceptance_discriminators[2]`
- **binding** — Deviation, input and resolution clauses span external counterexamples, acquisition permission and budget; route only actual facts to the named native suppliers, not to a new DES owner.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:n6-generation-cycle`, `write:n7-acquisition-bridge`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
