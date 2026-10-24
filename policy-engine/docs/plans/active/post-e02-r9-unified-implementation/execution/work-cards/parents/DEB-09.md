# DEB-09: родитель и соединение рабочих результатов

Canonical title: Institutional inputs and exact authority slots. R26 форма: `split`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/11-debt.md#DEB-09).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DEB-09.policy-signer](../cards/DEB-09/policy-signer.md) | [G06](../groups/G06.md) | Current purpose/scope/time-bound signer evidence authorizes only the intended epoch predicate-policy claim. |
| [DEB-09.transition-identity](../cards/DEB-09/transition-identity.md) | [G06](../groups/G06.md) | Transition-signing authority and producer identity bind to their intended claim role and remain distinct from policy signer and history holder. |
| [DEB-09.history-holder](../cards/DEB-09/history-holder.md) | [G06](../groups/G06.md) | Complete-history authenticity is established only by an independent holder whose admitted evidence covers the required history. |
| [DEB-09.delegation-mandate](../cards/DEB-09/delegation-mandate.md) | [G06](../groups/G06.md) | Separate DS15 delegation/mandate admission and Q02 current-principal exact amendment standing; neither substitutes for the other. |
| [DEB-09.epoch-qualification](../cards/DEB-09/epoch-qualification.md) | [G06](../groups/G06.md) | Signed policy and exact native relation are admitted only for intended purpose, scope and complete history. |
| [DEB-09.w5-crosswalk](../cards/DEB-09/w5-crosswalk.md) | [G06](../groups/G06.md) | Every original W5 route slot retains distinct meaning, owner, current status and evidence need; similar vocabulary is not equivalence. |

## Реальный join

policy-signer emits Role-specific source-qualified signer admission or typed-empty/refusal.; transition-identity emits Role-bound transition/producer admission or explicit typed-empty status.; history-holder emits Coverage-bound verified history receipt or typed incomplete-history refusal.; delegation-mandate emits Scope-bound delegation/mandate admission or typed-empty status.; epoch-qualification emits Purpose-scoped qualification/admission result with explicit typed refusal.; w5-crosswalk emits Versioned W5 row-to-role/scope/evidence crosswalk and unresolved slot list.. Root reconciles these exact outputs at the original parent disposition and sends the composed result to Fresh scientist/validation/decision_validity epoch/claim consumer and selected DS15 admission-bundle consumer.. This join does not create implementation, a second owner, or an extra start gate. Separately, delegation-mandate collects Q02 exact human-principal amendment standing from accepted history; root routes that scoped record to the existing amendment decision process and FINAL-USE only when the selected use depends on the amendment. Missing/contested standing leaves the amendment proposed and does not block authorized engineering under current rules.

**Outputs:** [DEB-09.policy-signer](../cards/DEB-09/policy-signer.md), [DEB-09.transition-identity](../cards/DEB-09/transition-identity.md), [DEB-09.history-holder](../cards/DEB-09/history-holder.md), [DEB-09.delegation-mandate](../cards/DEB-09/delegation-mandate.md), [DEB-09.epoch-qualification](../cards/DEB-09/epoch-qualification.md), [DEB-09.w5-crosswalk](../cards/DEB-09/w5-crosswalk.md).

**Fresh consumer / ответственный контур:** Fresh scientist/validation/decision_validity.py consumes role-bound epoch evidence only for a dependent authority claim; selected DS15 route admission consumes signed delegation/current mandate only when that route requires it. GYD-01 S7 HumanDecision and GYD-15 N8 remain their own applied consumers. Q02 standing goes separately to the existing amendment decision process and conditional FINAL-USE; no amendment is ratified by this intake.

**Review размера:** Five non-substitutable external roles require separate evidence slots; W5 crosswalk is a consumer/coordination result, not an appointment service.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — This is a shared non-substitution, status, authority-boundary, or slot-roster rule; parent_join reconciles distinct evidence outputs and does not invent suppliers.
  `task.deliverable`; `task.positive`; `task.adversarial`; `task.removal`; `task.surface`; `task.rollback`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.acceptance_ref`; `solution.implementation_steps[0]`; `solution.implementation_steps[2]`; `solution.implementation_steps[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[3]`; `solution.inputs_to_resolve[0]`; `solution.inputs_to_resolve[1]`
- **binding** — This is a shared non-substitution, status, authority-boundary, or slot-roster rule; parent_join reconciles distinct evidence outputs and does not invent suppliers.
  `task.migration`; `task.r19_extension.writer_rule`; `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`; `solution.composition_contracts[2]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:exact-path/{canonical_repo_path}`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
