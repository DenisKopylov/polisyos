# CAP-06.remote-effect-reconciliation — Persist and reconcile each remote operation

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [CAP-06](../../parents/CAP-06.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Every selected remote call has one exact intent/input/executable/recipient and a verifiable completed or indeterminate effect.

**Предпочтительное решение.** Persist LIF-04 intent and attempt in the existing ControlPlaneStore before sending through ControlWorker.dispatch_once; bind stable idempotency key, exact roots/query, executable and recipient, then use provider lookup/reconciliation on the same request. Lost replies remain pending/indeterminate; never blind-repeat or infer success. Anchors: runtime/http/services/control_plane_store.py; runtime/http/services/control_worker.py:ControlWorker.dispatch_once.

**Граница владельца.** CAP-06 provider-specific adapter consumes existing LIF-04/ControlPlaneStore owner. Parent native lease family: `write:exact-path/{canonical_repo_path}`. Exact post-E02 paths/overlap are unresolved; do not infer sibling disjointness or create a child lease. Root binds the actual path/lease before writes; cards sharing a native family serialize there.

**Входы.** Exact roots/query, executable/version, purpose/tenant/recipient, stable intent/key, provider lookup/cancel and attempt receipts.

**Выход и consumer.** Persisted attempt/effect receipt; lost or uncertain responses remain pending/indeterminate.

**Что можно готовить независимо.** Select provider semantics and freeze acquisition before replayable solver loops where possible.

**Где результат соединяется с другими.** Join same-key idempotency, current rights and actual provider response at each map call, retry, resume or cancel.

**Positive.** Same intent reconciles to one validated receipt and fresh consumer result without duplicate/lost effect.

**Distinguishing negative.** Lost response, expired key, changed recipient, cancel race, retry charge or nonreplayable solver effect cannot become success.

**Matched removal.** Remove actual receipt/recipient reconciliation but retain IDs; operation refuses or stays indeterminate.

**Граница контекста.** The card combines private/federated evidence qualification, durable remote effects/retries, and output-rights/sink enforcement. R15/R16/R17/R19 explicitly assign these to separate native owners; a single implementer otherwise holds statistical, provider, and custody contexts at once. This is one bounded property view; parent source pins, stage/dispatch, conditional acceptance and mandatory companions remain inherited.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted provider/source rebind where relevant; parent stage remains.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-02](../../parents/CAP-02.md) | `direct:interface_agreement; acceptance:composition`: Consume exact selected input roots at private/provider/effectful solver calls.<br>Source: `task.depends_on[1]`; `task.acceptance_dependencies[0]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [CAP-03](../../parents/CAP-03.md) | `direct:interface_agreement; acceptance:composition`: Consume exact admitted roots/current-use identity at input, dispatch, call and output admission.<br>Source: `task.depends_on[2]`; `task.acceptance_dependencies[1]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-04](../../parents/LIF-04.md) | `direct:interface_agreement; acceptance:composition`: Consume durable intent/effect for provider operations and each effectful solver call.<br>Source: `task.depends_on[3]`; `task.acceptance_dependencies[2]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement; acceptance:composition`: Consume shared rights/AP07 outcome at input, dispatch, calls, resume and sinks.<br>Source: `task.depends_on[4]`; `task.acceptance_dependencies[3]`.<br>Условия: original direct relation; source stage rules govern; selected parent composed claim; not a new preparation dependency |
| Composition output (не start gate) [CAP-06.rights-and-output-sinks](../../cards/CAP-06/rights-and-output-sinks.md) | Consume only for the exact composition described here: Join same-key idempotency, current rights and actual provider response at each map call, retry, resume or cancel. This link is not an unconditional all-of or preparation gate. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `CAP-06`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **execute** — LIF-04-backed provider adapter binds exact intent/input/executable/recipient, receipts, idempotency/recovery and provider limits; unknown effect stays pending/indeterminate.
  `solution.implementation_steps[0]`; `solution.implementation_steps[1]`; `solution.implementation_steps[2]`; `solution.free_grow.data_or_config_growth`; `solution.free_grow.resource_behavior`; `solution.composition_contracts[0]`; `solution.composition_contracts[3]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.deviation_triggers[0]`; `solution.inputs_to_resolve[1]`
- **binding** — A genuinely new remote protocol requires a reviewed typed adapter and selected-backend conformance; legacy or self-asserted completion is not executable evidence.
  `solution.free_grow.extension_boundary`
- **execute** — Migration/rollback preserves indeterminate legacy outcomes, blocks dispatch on compromise/revoke, reconciles in-flight effects before status changes and preserves exact receipts.
  `solution.migration_and_rollback`
- **execute** — bind the selected remote operation’s exact roots/executable/purpose/recipient and reconcile its result; do not infer statistical independence.
  `task.r19_extension.question_slices[0]` (`R18-D03-Q02`); `task.r19_extension.question_ids[0]` (`R18-D03-Q02`)
- **execute** — Current route matches for a selected remote transform: bind exact source/input/executable/build/evaluator/rule/attempt and make the fresh consumer reproduce from resolved bytes.
  `task.r19_extension.question_slices[1]` (`R18-D14-Q01`); `task.r19_extension.question_ids[1]` (`R18-D14-Q01`)
- **execute** — the selected remote capture needs a verifiable receipt/output bound to its recipient; completion/encryption is not meaning.
  `task.r19_extension.question_slices[3]` (`R18-D18-Q04`); `task.r19_extension.question_ids[6]` (`R18-D18-Q04`)
- **execute** — for selected private remote execution, reconcile the exact executable/effect receipt/recipient and keep uncertainty explicit.
  `task.r19_extension.question_slices[4]` (`R18-D17-Q01`); `task.r19_extension.question_ids[3]` (`R18-D17-Q01`)
- **execute** — retain sent/not-sent/indeterminate effect receipt and reconcile the same operation across rollout; no duplicate or lost effect.
  `task.r19_extension.question_slices[5]` (`R18-D17-Q02`); `task.r19_extension.question_ids[4]` (`R18-D17-Q02`)
- **execute** — for selected private remote calls, bind exact executable/input/recipient and a verified or indeterminate receipt to the observed process generation.
  `task.r19_extension.question_slices[6]` (`R18-D17-Q03`); `task.r19_extension.question_ids[5]` (`R18-D17-Q03`)

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
