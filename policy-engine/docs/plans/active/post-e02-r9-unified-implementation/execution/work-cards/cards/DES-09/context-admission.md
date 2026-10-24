# DES-09.context-admission — Ограничить контекст до разрешённого вызова

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [DES-09](../../parents/DES-09.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Each selected prompt/context/tool projection is bound to actual source, case, purpose, recipient, profile/envelope and rights; material counterevidence/qualifiers remain or explicit omissions are carried before egress.

**Предпочтительное решение.** Reuse the canonical traced gateway and prompt/tool ledger contract; bind exact retrieval/context, source-language/version, model/profile, tools, route/request and output refs. Treat summaries as derived candidates and verify material exceptions; do not collect hidden chain of thought or create authority from model output.

**Граница владельца.** DES-09 owns only shared invocation/context projection within write:traced-llm-context and write:prompt-tool-ledger. Existing OPS-07/CAP/LIF owners decide egress, budget, rights and lifecycle; this card records/consumes their actual decisions and cannot grant access. DES-02/05/06/08 own domain semantics. Exact overlap within the two lease families is one writer after E02 rebind.

**Входы.** Selected case/prompt/context and exact source/counterevidence/omissions; owner-resolved scope and per-call profile/envelope.; LIF-05 rights/current-use inputs and existing OPS/CAP conditions; input kind alone does not appoint or authorize a supplier.

**Выход и consumer.** A bounded, persisted, content-bound call context/projection with exact input and selection refs, purpose/recipient/profile and omitted qualifiers; disallowed context has no egress path.

**Что можно готовить независимо.** Context retrieval/compression and controlled exception/context-position cases can be prepared against the existing gateway after E02 rebind. Protected input projection waits for actual owner-authorized scope; no second model vote substitutes for this binding.

**Где результат соединяется с другими.** Pass admitted exact context to observed-call; persisted-call-record later joins actual call identity/output to the candidate and fresh domain consumer.

**Positive.** Different in-envelope contexts remain distinct call refs under one admitted profile; a selected legal call retains required norm dimensions and counterevidence.

**Distinguishing negative.** Context injection, missing source, profile-envelope escape, private query projection, lost legal exception or summary qualifier removal cannot inherit approval from a profile ID.

**Matched removal.** Remove actual content/envelope check but keep profile/context refs; an outside-envelope or exception-loss case is still accepted and the matched probe fails.

**Граница контекста.** This card governs context projection only; it is not a rights/egress authority owner. Actual content binding must be resolved against OPS/CAP/LIF decisions and exact E02 paths.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Every card consumes the accepted E02 source/commit and task-scoped source rebind for its own owner readback. The universal acceptance/stage/conditional gate remains the original parent contract; this map adds no second leaf gate or sequencing.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [LIF-05](../../parents/LIF-05.md) | `direct:interface_agreement`: Consumes the current rights/lifecycle basis for context projection; LIF-05 retains its permission and reuse owner.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `DES-09`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **execute** — The selected context projection is the first owned property; observed-call and persisted-call-record consume its actual admitted output.
  `task.deliverable`
- **join** — Bind exact per-call context/profile/envelope and reject an out-of-envelope call even when its profile marker is unchanged. The real gateway/ledger is the supplier; this route is not a new permission owner.
  `task.r19_extension.question_slices[0]`
- **binding** — Each source question ID is routed to the card assigned to its matching indexed question_slices clause in this parent; ID coverage preserves lineage and is not semantic proof.
  `task.r19_extension.question_ids[0]`
- **execute** — Implementation clause 1 belongs to context-admission: it binds actual gateway dispatch, selected context, persisted use, retry or truthful replay respectively; OPS/CAP/LIF keep their permits.
  `solution.implementation_steps[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
