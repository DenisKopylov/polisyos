# OPS-07.account-budget — Резервировать расход по billing principal

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-07](../../parents/OPS-07.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Concurrent attempts, retries and unknown outcomes reserve and reconcile once against the actual provider billing principal; an unknown charge remains reserved and is never treated as zero.

**Предпочтительное решение.** Reuse the current monetary/budget owner if it covers account-principal reservations; otherwise one minimal native core/security extension. ControlPlaneStore stores attempt references, not budget authority. Keep tenant quotas separate and version price/unit/window.

**Граница владельца.** One budget ledger owner under OPS-07 `write:exact-path/{canonical_repo_path}`; determine whether an existing owner already covers the billing principal at accepted-source rebind before any new extension. Provider and ControlPlaneStore are consumers, not extra budget writers.

**Входы.** Actual provider billing principal, price/unit/window, usage/charge and endpoint idempotency evidence; OPS-04/LIF-04 attempt and idempotency key; OPS-06 authorization for any call that is actually issued; OPS-07 secret-reference call identity without the secret value

**Выход и consumer.** Durable reservation/charge reconciliation receipt by principal, with unknown state distinct from zero; fresh operator/account-budget reader sees the remaining authorized ceiling.

**Что можно готовить независимо.** Budget contract and ledger owner can be resolved in accepted-source rebind. Before effect reserve approved maximum; unknown price/account basis permits only an owner-approved per-operation ceiling and an explicit account-unknown result.

**Где результат соединяется с другими.** Provider spend is independent from host resource caps and tenant quota; unknown remote effect retains full reservation. Secret resolution does not reset spend; account cap does not authorize a source action.

**Positive.** Concurrent calls reserve once to one billing principal and reconcile measured provider charges; ceiling behavior is exact on the selected price/window basis.

**Distinguishing negative.** Timeout, restart, retry, key rotation or connector switch keeps the reservation until positive reconciliation/idempotency evidence; incomplete metering cannot claim account-wide hard cap.

**Matched removal.** Remove principal binding/charge reconciliation but keep quota fields; the same concurrent unknown-charge case exceeds or falsely clears the approved ceiling.

**Граница контекста.** One spend authority only if the existing one cannot cover this binding. R14 model/trial/document work consumes this budget contract; no independent DES ledger. P04/P09/P37/P38 prevent unknown-as-zero and mismatched billing denominator.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Both owners and real consumers rebind to accepted E02 source before implementation; preserve parent acceptance stage.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Consume existing worker/durable attempt identity and retry/resume boundary; no new queue.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Secret scopes and issued provider calls consume the authorized grant; budget does not itself grant the effect.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:owner_readiness`: Use the existing attempt/cancellation/reconciliation identity; durable result remains with LIF-04.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-07`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for account-budget; selectors task.r14_extension.detail, task.r14_extension.quality_ref, task.r14_extension.product_verification, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.question_ids[2], solution.free_grow.extension_boundary, solution.free_grow.resource_behavior, solution.composition_contracts[1], solution.deviation_triggers[0], solution.inputs_to_resolve[1] remain load-bearing.
  `task.r14_extension.detail`; `task.r14_extension.quality_ref`; `task.r14_extension.product_verification`; `task.r19_extension.question_ids[0]`; `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[1]`
- **execute** — Direct result/preferred path for account-budget; selectors task.r14_extension.requirement, solution.implementation_steps[1], solution.implementation_steps[2] name the work and native owner seam.
  `task.r14_extension.requirement`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for account-budget; selectors task.r19_extension.question_slices[0], task.r19_extension.question_slices[1], task.r19_extension.question_slices[2], solution.acceptance_discriminators[1] are checked at its actual reader/sink. Bundled subclauses: U026:{"question_id":"R18-D16-Q01","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q01","mechanism_ids":["S16-M1"],"role":"input collection"}; U027:{"question_id":"R18-D19-Q02","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q02","mechanism_ids":["S19-M1","S19-M2"],"role":"input collection"}; U028:{"question_id":"R18-D19-Q04","solution_ref":"solutions/lifecycle-r19/S19.md#r18-d19-q04","mechanism_ids":["S19-M1","S19-M2"],"role":"input collection"}.
  `task.r19_extension.question_slices[0]`; `task.r19_extension.question_slices[1]`; `task.r19_extension.question_slices[2]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
