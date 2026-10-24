# DES-09.persisted-call-record — Связать вызов с сохранённым результатом

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [DES-09](../../parents/DES-09.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A fresh consumer can resolve the permitted observed invocation, exact context and output/candidate use, usage/cost and replay limits; cancellation or missing persistence never leaves a phantom success.

**Предпочтительное решение.** Persist permitted input/output/source refs, tool choices, actual role in the candidate and usage under the existing prompt/tool ledger. Protect secrets/restricted prompts in artifacts and logs. Bind candidate result to invocation identity, not model labels or summary embeddings.

**Граница владельца.** DES-09 owns the shared ledger projection under write:prompt-tool-ledger; observed-call provides actual invocation facts and context-admission provides selected context. DES-02/05/06/08 are consuming domain owners; OPS/CAP/LIF retain their authority and resource decisions. Shared lease remains one writer after E02 exact-path rebind.

**Входы.** observed-call event and context-admission exact selection; permitted output/artifact refs and actual usage/cost.; Existing consumer contracts in DES-02/05/06/08; no task creates a domain semantic gate or second invocation service.

**Выход и consumer.** Persisted call/use record resolvable in a fresh operational/audit reader, with actual identity, context, output use, cost, cancellation/retry state and replay limitation.

**Что можно готовить независимо.** Ledger projection and consumer cases may be prepared independently against agreed contracts; no observed call is required to prepare them. A live-call result remains UNRUN until observed; restricted prompt bytes remain unavailable where existing rights do not allow them.

**Где результат соединяется с другими.** Fresh call-ledger and selected domain consumers join observation, context, candidate/output and usage. An authorized audit view exposes safe refs without leaking protected prompt content.

**Positive.** A real permitted call resolves from exact context through persisted candidate to actual usage; a second process can read the reference, and missing-provider mode shows no fabricated invocation.

**Distinguishing negative.** Lost persistence, phantom success after cancellation, secret leakage, summarized rare-row inference, no-call labels or stale incompatible cache cannot establish the chain.

**Matched removal.** Retain count/model/ledger labels but remove actual invocation record or decisive context binding; fresh provenance/semantic reader detects loss.

**Граница контекста.** This is the persisted consumer endpoint, not a second provider gateway. Bundled end-to-end clauses reconcile actual context and observed-call suppliers; shared ledger remains single-writer.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [DES-09.context-admission](../../cards/DES-09/context-admission.md) | Only for the selected same-scope composition described by this card: Fresh call-ledger and selected domain consumers join observation, context, candidate/output and usage. An authorized audit view exposes safe refs without leaking protected prompt content. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [DES-09.observed-call](../../cards/DES-09/observed-call.md) | Only for the selected same-scope composition described by this card: Fresh call-ledger and selected domain consumers join observation, context, candidate/output and usage. An authorized audit view exposes safe refs without leaking protected prompt content. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-09`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **join** — Actual invocation/context removal and cancelled-phantom-result are detected at the persisted fresh consumer, with context and observed-call suppliers named.
  `task.removal`
- **join** — Authorized operational/audit view is the persisted-use reader; secret content stays within existing rights.
  `task.surface`
- **join** — Bind actual advice shown in the randomized case to observed invocation, selected context and edition; label no-call/withheld distinctly. The real gateway/ledger is the supplier; this route is not a new permission owner.
  `task.r19_extension.question_slices[1]`
- **join** — Persist the actual call/context/output identity and denominator; rare-row summaries cannot substitute for a missing row. The real gateway/ledger is the supplier; this route is not a new permission owner.
  `task.r19_extension.question_slices[2]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[1]`; `task.r19_extension.question_ids[2]`
- **execute** — Implementation clause 2 belongs to persisted-call-record: it binds actual gateway dispatch, selected context, persisted use, retry or truthful replay respectively; OPS/CAP/LIF keep their permits.
  `solution.implementation_steps[2]`
- **join** — Acceptance discriminators require actual call/context/output/usage persistence and a fresh consumer; bundled lost-qualifier/no-call cases reconcile context-admission and observed-call suppliers.
  `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`; `solution.acceptance_discriminators[2]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
