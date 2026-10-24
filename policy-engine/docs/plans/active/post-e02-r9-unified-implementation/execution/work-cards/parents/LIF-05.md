# LIF-05: родитель и соединение рабочих результатов

Canonical title: Fence rights-sensitive materialization, deletion and restore. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/02-custody.md#LIF-05).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [LIF-05.rights_decision](../cards/LIF-05/rights_decision.md) | [G06](../groups/G06.md) | One qualified decision binds authority/action/purpose/audience/unit/overlap/effective time; retention default is not grant. |
| [LIF-05.sink_egress_fence](../cards/LIF-05/sink_egress_fence.md) | [G08](../groups/G08.md) | Actual CAP03/06 sink reserves/commits under current decision; uncertain disclosure is held. |
| [LIF-05.placement_restore_and_retained_use](../cards/LIF-05/placement_restore_and_retained_use.md) | [G07](../groups/G07.md) | Each actual placement receives a rights/retention/existence decision against post-backup history and currentness; LIF05 does not decide physical restore enablement. |

## Реальный join

Join rights_decision (qualified source-use decision/generation), sink_egress_fence (actual per-sink commit/hold), and placement_restore_and_retained_use (per-placement rights/retention/existence result). OPS05 alone owns physical restore/quarantine/cut/continuity and enablement, consuming the LIF05 placement result with LIF02 material Claim/public-history reconciliation; no second admission bit.

**Outputs:** [LIF-05.rights_decision](../cards/LIF-05/rights_decision.md), [LIF-05.sink_egress_fence](../cards/LIF-05/sink_egress_fence.md), [LIF-05.placement_restore_and_retained_use](../cards/LIF-05/placement_restore_and_retained_use.md).

**Fresh consumer / ответственный контур:** CAP03/06 actual admission and sink consumers; OPS-05 physical restore/quarantine/continuity/enablement consumer; fresh authorized restored-artifact/claim reader.

**Review размера:** 3 outputs retain native lease family. Pattern pass P05/P09/P15/P27/P29/P32/P37/P38/P40/P41; no all-copy/zeroization claims, behavioral sink/restore probe.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Aggregate combines three actual card outputs.
  `task.deliverable`
- **join** — Bundled revoke/stream/copies/restore/expiry races cross owners.
  `task.adversarial[0]`
- **join** — Surface and rights-aware rollback span outputs.
  `task.surface`; `task.rollback`
- **binding** — Shared acceptance/review/companions.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.rollback_precedence`
- **binding** — R14 refs/status.
  `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`
- **binding** — R15 refs/status.
  `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.product_verification`
- **join** — R17 hold/erase/egress/restore clauses cross cards.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.delivery_slices[1]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`; `task.r17_extension.quality_cases[3]`; `task.r17_extension.quality_cases[4]`; `task.r17_extension.product_verification`
- **binding** — R19 metadata.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Writer rule/ref.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **join** — Typed external evidence and OPS05/LIF02 restore-currentness composed.
  `solution.composition_contracts[2]`; `solution.composition_contracts[3]`
- **join** — Multi-card adversarial and removals.
  `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`
- **join** — Conditional non-atomic boundary.
  `solution.deviation_triggers[2]`
- **binding** — Input rule.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:governed-copy`, `resource:cas/{tenant}/{cell}/{root}`, `write:semantic-owner/source-disclosure`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
