# DES-09.observed-call — Зафиксировать фактически выполненный вызов

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DES-09](../../parents/DES-09.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A permitted live call, replay, cache hit, retry, cancellation or partial result is distinguished from configured client/profile markers and is released only through the existing authorized gateway.

**Предпочтительное решение.** Reuse existing traced gateway, provider/recipient capture and resource/cancellation owners. Observe actual returned provider/model/profile/version/settings/usage; distinguish recorded-response reconstruction, deterministic replay and fresh stochastic run. Unknown internals limit reproducibility rather than invent it.

**Граница владельца.** DES-09 owns invocation observation in write:traced-llm-context and write:prompt-tool-ledger. OPS-07/CAP/LIF retain permits, egress, rights, cost, cancellation and lifecycle; no source code execution from model text through G6. Exact shared paths need single-writer resolution after E02 rebind.

**Входы.** context-admission exact context and purpose/recipient; actual gateway dispatch/cancellation result.; Existing provider credentials, selected model profile and OPS/CAP permission/budget; if absent, no live-call claim and existing allowed grammar work remains.

**Выход и consumer.** A truthful observed invocation event distinguishing fresh call, cache, recorded replay, deterministic replay, no-call, cancelled, partial and indeterminate outcomes, with actual returned identity and usage refs.

**Что можно готовить независимо.** Gateway instrumentation and timeout/retry/cancel/cache cases may be prepared independently against the agreed gateway interface after E02 rebind. Live proof requires actual provider permit/credentials and selected profile; no external act is invented.

**Где результат соединяется с другими.** At an actual permitted call, consume the admitted exact context and persist the observed call identity/output for the call-record reader; actual release remains evaluated by the existing authorized gateway owner, not by ledger presence.

**Positive.** A permitted real call is observed with actual provider/model/recipient identity and usage; deterministic or recorded fallback is labelled separately.

**Distinguishing negative.** Client without call, alias/version drift, retry of a sent/indeterminate effect as not-sent, stale cache across rights/epoch/model/purpose, or revocation before fenced release cannot be green.

**Matched removal.** Keep configured model/version and ledger markers but stub actual provider dispatch or recipient gate; controlled canary observes no valid release and the claim fails.

**Граница контекста.** The actual call remains conditional on external/owner permission. This card observes the existing gateway path and must not create a parallel provider or permission service.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Source: `task.depends_on[0]`.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-07](../../parents/OPS-07.md) | `direct:interface_agreement`: Consumes actual provider/egress/resource permit result at the existing gateway; OPS-07 remains permit owner.<br>Source: `task.depends_on[2]`.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DES-09.context-admission](../../cards/DES-09/context-admission.md) | Only for the selected same-scope composition described by this card: At an actual permitted call, consume the admitted exact context and persist the observed call identity/output for the call-record reader; actual release remains evaluated by the existing authorized gateway owner, not by ledger presence. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles применяются на своей стадии. Composition links не задают порядок независимой подготовки.

## Назначенный нормативный контекст

Source-manifest base: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`; это не plan_commit назначения. Точные immutable blobs/hash — [coverage.json](../../coverage.json), parent `DES-09`. `task` выбирает строку tasks.json по id, `solution` — preferred-solutions.json по task_id; затем dot/index selector. Для R19 identity определяется значением question_id, не позицией в другом массиве. Полностью прочитайте назначенные fragments и нужные contracts; mixed clause нельзя усечь.

- **join** — The bundled adversarial clause includes context injection/private-query projection, provider/cache drift, lost legal exception and no-call; observed-call must consume context-admission and actual gateway/OPS decisions for each subclause.
  `task.adversarial`
- **binding** — Permitted provider access/credentials and selected model profile are conditions of the actual call; their absence leaves live proof UNRUN.
  `task.genuine_external_inputs[0]`
- **join** — R17 real release/recipient/delegation and sent/indeterminate retry semantics are exercised at the existing gateway, never inferred from handoff or ledger markers.
  `task.r17_extension.requirement`; `task.r17_extension.positive`; `task.r17_extension.adversarial`; `task.r17_extension.removal`; `task.r17_extension.delivery_slices[0]`; `task.r17_extension.quality_cases[0]`; `task.r17_extension.quality_cases[1]`; `task.r17_extension.product_verification`
- **execute** — Preferred solution reuses actual gateway/provider/resource owners; context and persistence are explicit sibling checkpoints.
  `solution.preferred_solution`
- **execute** — Implementation clause 0 belongs to observed-call: it binds actual gateway dispatch, selected context, persisted use, retry or truthful replay respectively; OPS/CAP/LIF keep their permits.
  `solution.implementation_steps[0]`
- **execute** — Implementation clause 3 belongs to observed-call: it binds actual gateway dispatch, selected context, persisted use, retry or truthful replay respectively; OPS/CAP/LIF keep their permits.
  `solution.implementation_steps[3]`
- **execute** — Implementation clause 4 belongs to observed-call: it binds actual gateway dispatch, selected context, persisted use, retry or truthful replay respectively; OPS/CAP/LIF keep their permits.
  `solution.implementation_steps[4]`
- **execute** — Bind actual invocation identity/request/output; context admission and persisted use are separate checkpoints.
  `task.r19_extension.question_slices[0]` (`R18-D11-Q01`); `task.r19_extension.question_ids[0]` (`R18-D11-Q01`)
- **execute** — Observe actual provider/model/recipient and distinguish call/cache/replay.
  `task.r19_extension.question_slices[3]` (`R18-D17-Q03`); `task.r19_extension.question_ids[3]` (`R18-D17-Q03`)
- **execute** — Capture requested and returned identity; alias cannot hide drift.
  `task.r19_extension.question_slices[4]` (`R18-D17-Q04`); `task.r19_extension.question_ids[4]` (`R18-D17-Q04`)

### Обязанности внутри составных fragments

- `task.r19_extension.question_slices[1]` — Record actual advice presentation as call/cache/replay or no-call. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).
- `task.r19_extension.question_slices[2]` — Bind durable record to observed actual call, not configured profile. (primary accountability остаётся в coverage; это конкретный подрезультат, не второй writer).

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
