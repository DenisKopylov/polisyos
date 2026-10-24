# LIF-04: родитель и соединение рабочих результатов

Canonical title: Preserve long-running duty across retry, cancel and uncertain effects. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/02-custody.md#LIF-04).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-04.effect_recovery](../cards/LIF-04/effect_recovery.md) | [G09](../groups/G09.md) | Stable intent/request digest reconciles attempts to one effect; unknown differs from success/cancel/unavailable. |
| [LIF-04.durable_service_commitment](../cards/LIF-04/durable_service_commitment.md) | [G07](../groups/G07.md) | Duty retains identity, version/terms, age and due trigger across restart/review/policy change. |
| [LIF-04.trial_recovery_consumer](../cards/LIF-04/trial_recovery_consumer.md) | [G05](../groups/G05.md) | Fresh consumer resolves one qualified realization per native intent with honest late/duplicate dependence. |

## Реальный join

Join outputs effect_recovery (persisted provider effect/recovery state), durable_service_commitment (versioned due/continuation/outcome), and trial_recovery_consumer (one accepted realization per intent) only at their actual readers. Review is not execution; LIF02 joins duty outcomes only when claim coverage is enrolled; DES03/GYD30 keep trial identity.

**Outputs:** [LIF-04.effect_recovery](../cards/LIF-04/effect_recovery.md), [LIF-04.durable_service_commitment](../cards/LIF-04/durable_service_commitment.md), [LIF-04.trial_recovery_consumer](../cards/LIF-04/trial_recovery_consumer.md).

**Fresh consumer / ответственный контур:** Fresh runtime status/audit reader, selected DES03/GYD30 trial consumer, and LIF-02 enrolled claim reader only under its conditional promise.

**Review размера:** 3 cards retain R25 effect/service and separate native trial consumer. Pattern pass P01/P02/P04/P09/P27/P29/P32/P37/P38; probe lost reply, due restart and late same-intent result.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Review/companions/precedence.
  `task.acceptance_steps[9]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **binding** — R16 refs/status.
  `task.r16_extension.delivery_slices[0]`; `task.r16_extension.delivery_slices[1]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.product_verification`
- **binding** — R17 refs/status/owner.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.delivery_slices[2]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — IDs/owner/ref.
  `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `task.r19_extension.question_ids[3]`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **binding** — Input rule.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:runtime-duty`, `resource:control/{cell}/outbox`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
