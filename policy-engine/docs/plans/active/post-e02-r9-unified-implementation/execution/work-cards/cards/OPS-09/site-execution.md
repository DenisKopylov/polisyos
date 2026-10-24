# OPS-09.site-execution — Исполнять запрос внутри сети custodial site

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-09](../../parents/OPS-09.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected site worker consumes one valid existing durable job/lease generation and emits a source/version-bound attempt result or explicit unresolved outcome while raw data and secret remain in the custodian boundary.

**Предпочтительное решение.** Use a pull-only worker inside source custodian network composed with ControlWorker/LIF-04 lease and receipt. Extend existing connector/site runtime only; no second queue, remote result authority or scheduler.

**Граница владельца.** OPS-09 exact writes remain under `write:exact-path/{canonical_repo_path}` and selected site-worker/runtime owner. OPS-04/LIF-04 owns durable lease/effect, CAP-06 owns private/federated intake/roster, OPS-06 source rights, OPS-07 secrets, OPS-08 physical limit. Resolve site path and overlapping lease only after E02 rebind.

**Входы.** CAP-06 agreed bounded request, input/roster and result/receipt contract; OPS-04/LIF-04 actual lease generation, attempt, cancellation/reconciliation; OPS-06 current source action grant; OPS-07 ephemeral scoped credential; OPS-08 selected measured host envelope; Site worker contract/version and custodian host identity

**Выход и consumer.** Attempt-bound execution receipt with source/version and result digest plus actual roster/omission/unresolved-effect facts, consumed by CAP-06/CNT-06 and existing result reader.

**Что можно готовить независимо.** Site worker contract and reader can be prepared after interface agreement. Protected source query waits for selected commissioning, grant, lease, secret, and site egress/custody proof; this tier is selected only under OPS-09 override.

**Где результат соединяется с другими.** Execution completion is distinct from output permission/admission, population/inference validity and later reuse. CAP-06 binds input/result intake; CNT-06 qualifies inference; OPS-06/07 and LIF-05 control separate action/copy boundaries.

**Positive.** A permitted bounded query executes in the actual custodian cell and returns a source/version-bound unresolved-or-complete attempt receipt while raw bytes remain local.

**Distinguishing negative.** Invalid lease, site worker/version mismatch, nonrandom dropout, misaligned/duplicate site, crash dump/temp/cache leak or uncertain effect cannot retain a broad numerical/currentness claim.

**Matched removal.** Remove actual site worker contract/generation, roster/source binding or observed egress check while keeping hybrid/deployment markers; the selected consumer must remain limited/refuse.

**Граница контекста.** G09 is the worker/custodian deployment home. The R15/R16 private result still belongs to CAP-06/CNT-06 scientific consumers; a secure call does not own inference or output authority. Conditional tier and no-parity contract stay at parent.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Selected tier is rebound to accepted E02 source; conditional selection remains the parent override.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-04.external-runner](../../cards/OPS-04/external-runner.md) | `direct:owner_readiness`: Consume the existing durable worker/lease lifecycle; no new queue or remote scheduler.<br>Source: `task.depends_on[1]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-05](../../parents/OPS-05.md) | `direct:owner_readiness`: Consume selected retained-state/receipt and restore evidence only for the activated site workflow.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Current source/query authority is consumed before run and at actual recipient release; it is not supplied by credentials or network policy.<br>Source: `task.depends_on[3]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-07](../../parents/OPS-07.md) | `direct:owner_readiness`: Consume a JIT secret reference only; credential validity does not grant source permission.<br>Source: `task.depends_on[4]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-08](../../parents/OPS-08.md) | `direct:owner_readiness`: Consume selected measured worker/site envelope when this tier is activated.<br>Source: `task.depends_on[5]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-06](../../parents/CAP-06.md) | `direct:owner_readiness`: CAP-06 owns private/federated input/result intake, roster and output-right handshake; OPS-09 only executes the selected site path.<br>Source: `task.depends_on[6]`.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `OPS-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for site-execution; selectors task.rollback, task.migration, task.r15_extension.detail, task.r15_extension.quality_ref, task.r15_extension.technical_profiles[0], task.r15_extension.product_verification, task.r16_extension.delivery_slices[0], task.r16_extension.product_verification, task.r17_extension.delivery_slices[0], task.r17_extension.product_verification, task.r19_extension.status, task.r19_extension.product_verification, task.r19_extension.composition_contract_ref, task.r19_extension.question_ids[0], task.r19_extension.question_ids[1], task.r19_extension.writer_rule, task.r19_extension.acceptance_ref, solution.free_grow.data_or_config_growth, solution.free_grow.extension_boundary, solution.free_grow.resource_behavior remain load-bearing.
  `task.rollback`; `task.migration`; `task.r15_extension.detail`; `task.r15_extension.quality_ref`; `task.r15_extension.technical_profiles[0]`; `task.r15_extension.product_verification`; `task.r16_extension.delivery_slices[0]`; `task.r16_extension.product_verification`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.product_verification`; `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`; `task.r19_extension.writer_rule`; `task.r19_extension.acceptance_ref`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`
- **execute** — Direct result/preferred path for site-execution; selectors task.r15_extension.requirement, task.r16_extension.requirement, task.r17_extension.requirement, solution.implementation_steps[0], solution.implementation_steps[1], solution.implementation_steps[2] name the work and native owner seam.
  `task.r15_extension.requirement`; `task.r16_extension.requirement`; `task.r17_extension.requirement`; `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for site-execution; selectors task.r15_extension.positive, task.r15_extension.adversarial, task.r15_extension.removal, task.r16_extension.positive, task.r16_extension.adversarial, task.r16_extension.removal, task.r16_extension.quality_cases[0], task.r16_extension.quality_cases[1], task.r16_extension.quality_cases[2], task.r16_extension.quality_cases[3], task.r16_extension.quality_cases[4], task.r17_extension.positive, task.r17_extension.adversarial, task.r17_extension.removal, task.r17_extension.quality_cases[0], task.r17_extension.quality_cases[1], task.r17_extension.quality_cases[2], task.r19_extension.question_slices[1] are checked at its actual reader/sink. Bundled subclauses: U051:{"question_id":"R18-D17-Q01","solution_ref":"solutions/lifecycle-r19/S17.md#r18-d17-q01","mechanism_ids":["S17-M1","S17-M2","S17-M4"],"role":"primary writer"}.
  `task.r15_extension.positive`; `task.r15_extension.adversarial`; `task.r15_extension.removal`; `task.r16_extension.positive`; `task.r16_extension.adversarial`; `task.r16_extension.removal`; `task.r16_extension.quality_cases[0]`; `task.r16_extension.quality_cases[1]`; `task.r16_extension.quality_cases[2]`; `task.r16_extension.quality_cases[3]`; `task.r16_extension.quality_cases[4]`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.quality_cases[2]`
- **join** — The selected hybrid site's actual worker contract/generation and bounded source-side result are the site execution owner's evidence; a stable public API/worker label is not enough.
  `task.r19_extension.question_slices[1]` (`R18-D17-Q01`); `task.r19_extension.question_ids[0]` (`R18-D17-Q01`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[0]` — Supply the attempt-bound result/receipt and digest; execution completion does not authorize release. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
