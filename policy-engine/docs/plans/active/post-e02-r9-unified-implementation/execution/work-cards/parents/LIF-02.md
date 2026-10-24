# LIF-02: родитель и соединение рабочих результатов

Canonical title: Enroll source dependencies and fence currentness at publication. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/02-custody.md#LIF-02).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-02.native_event_replay](../cards/LIF-02/native_event_replay.md) | [G07](../groups/G07.md) | At C/W replay (C,W], refuse passed floor, couple dedupe/effect, append invalidation and fence on source/right cut. |
| [LIF-02.bounded_observation_order](../cards/LIF-02/bounded_observation_order.md) | [G07](../groups/G07.md) | No-feed basis binds CAP04 to CAP02 root/profile/coverage and ordered attempt/head; never fabricates event. |
| [LIF-02.conditional_duty_join](../cards/LIF-02/conditional_duty_join.md) | [G07](../groups/G07.md) | Missed committed interval limits only enrolled claims dependent on selected duty. |

## Реальный join

One currentness owner reconciles outputs native_event_replay (source-native C/W replay/publication fence), bounded_observation_order (local ordered observation/as-of basis), and conditional_duty_join (scoped duty result). CAP04 event/observation receipts and selected LIF04/OPS11/LIF06/OPS08 witnesses join only at their canonical composition conditions. No synthetic event; due outage remains observable without event/heartbeat.

**Outputs:** [LIF-02.native_event_replay](../cards/LIF-02/native_event_replay.md), [LIF-02.bounded_observation_order](../cards/LIF-02/bounded_observation_order.md), [LIF-02.conditional_duty_join](../cards/LIF-02/conditional_duty_join.md).

**Fresh consumer / ответственный контур:** Fresh Decision Validity/currentness and selected UI-02/UI-19/API history readers; LIF-09.vertical_witnesses/final_join_receipt consumes the actual CAP-04 event and selected LIF-02 outputs at composition.

**Review размера:** 3 checkpoints one lease; paths unresolved. Pattern pass P04/P07/P08/P09/P29/P32/P35/P37/P38. Acceptance: no-feed pre-enrollment, A/B/A, missed due only affects enrolled claim.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **binding** — Shared E02 acceptance procedure.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`
- **binding** — Review/companions/journal/precedence.
  `task.acceptance_steps[7]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **binding** — R15 refs/status.
  `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.technical_profiles[3]`; `task.r15_extension.product_verification`
- **binding** — R16 refs/status.
  `task.r16_extension.delivery_slices[0]`; `task.r16_extension.delivery_slices[1]`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.product_verification`
- **binding** — R17 refs/owner.
  `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.delivery_slices[2]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.quality_cases[5]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Writer rule/ref.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **binding** — Parent input rule.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:claim-currentness`, `resource:source/{source_profile}/generation`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
