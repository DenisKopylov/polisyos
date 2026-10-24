# CNT-06: родитель и соединение рабочих результатов

Canonical title: Ground empirical, causal, transport and calibration claims (W3). R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/09-foundations.md#CNT-06).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [CNT-06.causal-support](../cards/CNT-06/causal-support.md) | [G03](../groups/G03.md) | Each causal ClaimRecord binds actual evidence, intervention/version, target, comparator, outcome/horizon, estimand, method, assumptions and contrary evidence; support is bounded by identification/transport/selection/interference/overlap. |
| [CNT-06.prediction-calibration](../cards/CNT-06/prediction-calibration.md) | [G03](../groups/G03.md) | Only a selected prediction claim whose method profile requires calibration gets a versioned calibration relation tied to target, horizon, permitted independent labels and protocol; calibration is not causal identification. |

## Реальный join

Fresh Scientist/G2–G6 readers consume qualified causal-support and prediction-calibration only where their claim profile requires them. For selected structural learning, causal-support feeds GYD-12.structural-write with proposition/regime/identification/rivals/lineage/uncertainty; O3 alone appends WMR and a fresh later-cycle reader checks it. No causal-card direct WMR write and no universal structural-append/calibration gate.

**Outputs:** [CNT-06.causal-support](../cards/CNT-06/causal-support.md), [CNT-06.prediction-calibration](../cards/CNT-06/prediction-calibration.md).

**Fresh consumer / ответственный контур:** Existing Scientist ClaimRecord workflow consumer plus selected G2/G3/G4/G5/G6 reader; predictive reader is conditional and must be identified on E02 rebind.

**Review размера:** Split causal identification/transport from prediction calibration due to distinct method, supplier and validator. Causal completion can stand without calibration under its own method profile.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Deliverable, external-source and end-to-end positive/adversarial clauses cover causal support plus conditional calibration; parent reconciles both outputs and does not require calibration universally.
  `task.deliverable`; `task.external_inputs`; `task.positive`; `task.adversarial`
- **join** — The uncertainty/dependency audit surface can expose both inferential relations; parent composes outputs without a new surface owner.
  `task.surface[1]`
- **binding** — Common source-rebind/oracle/native-path/fresh-consumer/review steps and mandatory schema/consumer/migration/journal/review companions remain in the parent contract.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`; `task.acceptance_evidence_requirements[0]`
- **binding** — R15 detail/quality and TP02/03/07/08 references plus UNRUN are canonical navigation/status; substantive research clauses route to causal-support.
  `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.technical_profiles[1]`; `task.r15_extension.technical_profiles[2]`; `task.r15_extension.technical_profiles[3]`; `task.r15_extension.product_verification`
- **binding** — R16 product verification is UNRUN status, not implementation evidence.
  `task.r16_extension.product_verification`
- **binding** — R17 UNRUN and R19 planned/UNRUN/composition refs are parent status/navigation fields.
  `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — R19 question IDs, native-owner writer rule and assurance reference preserve canonical source navigation and leases; the 15 semantic slices are routed to causal-support.
  `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`
- **binding** — Transport and calibration are separate validation relations; parent join preserves distinct outputs and never makes one a substitute or blanket prerequisite.
  `solution.composition_contracts[1]`
- **binding** — Input-resolution rule separates internal method/claim bridge work from actual study, reviewer and validation-label suppliers.
  `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
