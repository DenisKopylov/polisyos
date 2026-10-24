# DES-09: родитель и соединение рабочих результатов

Canonical title: Bind real LLM execution, contextual evidence and resource use to native ledgers. R26 форма: `sequence`. [Task manifest](../../../tasks.json) · [Preferred solution](../../../solutions/13-productive-design.md#DES-09).

Эта страница — родительская accountability, не дополнительная дробная карточка и не второй implementation owner. Полный source scope сохраняется.

| Карточка | Группа | Observable результат |
|---|---|
| [DES-09.context-admission](../cards/DES-09/context-admission.md) | [G06](../groups/G06.md) | Each selected prompt/context/tool projection is bound to actual source, case, purpose, recipient, profile/envelope and rights; material counterevidence/qualifiers remain or explicit omissions are carried before egress. |
| [DES-09.observed-call](../cards/DES-09/observed-call.md) | [G09](../groups/G09.md) | A permitted live call, replay, cache hit, retry, cancellation or partial result is distinguished from configured client/profile markers and is released only through the existing authorized gateway. |
| [DES-09.persisted-call-record](../cards/DES-09/persisted-call-record.md) | [G09](../groups/G09.md) | A fresh consumer can resolve the permitted observed invocation, exact context and output/candidate use, usage/cost and replay limits; cancellation or missing persistence never leaves a phantom success. |

## Реальный join

Reconcile exact selected context, real observed gateway result, persisted invocation/use record and fresh reader. DES-09 supplies no prompt authority or egress grant; live-provider evidence stays UNRUN absent the actual OPS/CAP/LIF permissions and observed call.

**Outputs:** [DES-09.context-admission](../cards/DES-09/context-admission.md), [DES-09.observed-call](../cards/DES-09/observed-call.md), [DES-09.persisted-call-record](../cards/DES-09/persisted-call-record.md).

**Fresh consumer / ответственный контур:** Fresh prompt/tool-ledger reader on an actual DES-02 N4 call, with DES-05/DES-06/DES-08 consuming their selected domain call records under their own rights and semantics.

**Review размера:** Three ordered outputs separate context admission, observed external call, and persisted record/fresh consumer. DES-09 owns one shared projection/ledger writer; DES-02/05/06/08 own their domain semantics, and OPS/CAP/LIF keep authority.

Ниже сохранённые parent-wide clauses, а не разрешение спрятать реализацию. Они должны быть доказаны outputs названных карточек, собственным coordination decision или настоящим external input. Shared constraint сам не является выполненной работой.

- **join** — Shared parent acceptance and mandatory companions are reconciled across context, gateway and persisted-use outputs.
  `task.acceptance_steps[0]`; `task.acceptance_steps[1]`; `task.acceptance_steps[2]`; `task.acceptance_steps[3]`; `task.acceptance_steps[4]`; `task.mandatory_companions[0]`; `task.mandatory_companions[1]`; `task.mandatory_companions[2]`; `task.mandatory_companions[3]`; `task.mandatory_companions[4]`
- **join** — Positive bundles actual context, live call, persisted candidate and usage; root composes all three rather than declaring a context marker sufficient.
  `task.positive`
- **binding** — Rollback/migration apply to all invocation records and current rights; preserve immutable history and newer revocations.
  `task.rollback`; `task.migration`
- **binding** — R19 status, verification and parent composition ref remain inherited parent-level call contract.
  `task.r19_extension.status`; `task.r19_extension.product_verification`; `task.r19_extension.composition_contract_ref`
- **binding** — Single native invocation projection/ledger writer and cross-owner consumer rule is parent-wide; exact path overlap is resolved by E02 rebind.
  `task.r19_extension.writer_rule`
- **binding** — Acceptance reference applies to all call/context/persistence outputs.
  `task.r19_extension.acceptance_ref`
- **binding** — Free-grow, semantic version, resource/rights and rollback constraints span the parent; no new domain template, credential or cancellation owner.
  `solution.free_grow.data_or_config_growth`; `solution.free_grow.extension_boundary`; `solution.free_grow.resource_behavior`; `solution.migration_and_rollback[0]`; `solution.migration_and_rollback[1]`
- **binding** — DES-02/05/06/08 consume the shared call contract; they keep their domain semantics, while OPS/CAP/LIF retain permits/egress/lifecycle.
  `solution.composition_contracts[0]`
- **binding** — Interface agreement may permit prep, but live call still needs actual rights/resource permits and model text cannot execute through G6.
  `solution.composition_contracts[1]`
- **binding** — Deviation and external-input resolution are parent-wide; missing provider/credential is external for live proof, while missing adapter is internal engineering.
  `solution.deviation_triggers[0]`; `solution.deviation_triggers[1]`; `solution.deviation_triggers[2]`; `solution.inputs_to_resolve[0]`; `solution.input_resolution_rule`

## Owners и stages

**Canonical lease namespace:** `write:traced-llm-context`, `write:prompt-tool-ledger`. Это namespace исходного parent, не доказательство disjoint write sets карточек. P0 binds exact paths/generated owner и пофазовые ресурсы.

Все inherited fields перечислены в [coverage.json](../coverage.json); `scope`, source IDs/debt refs, stage/phase, acceptance/conditional/execution и allocation rules сохраняют смысл canonical manifest. Producer-card links — выбранный плановый маршрут; actual source-qualified input всё равно обязателен на своей стадии.

До фактической приёмки E02 — только документация. Общий [порядок R26](../README.md) и [stage contract](../../05-stage-and-release-contracts.md).
