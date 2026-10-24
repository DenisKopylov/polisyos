# OPS-09.output-release — Выпускать только разрешённый результат exact recipient

Группа: [G06 — Допустимость, полномочия и квалифицированные решения](../../groups/G06.md). Родитель: [OPS-09](../../parents/OPS-09.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only the exact cleared result reaches the granted recipient after a current source/right and recipient/output decision at the irreversible release boundary; completed execution or encryption alone is insufficient.

**Предпочтительное решение.** Reuse OPS-06 semantic source/right authority and LIF-05 copy/retention/sink policy at the actual connector/output sink. Consume the site receipt/result; keep custodian-controlled network and local-copy enforcement with the institution.

**Граница владельца.** This card does not write the source permission or custody/copy ledger; any OPS-09 sink integration stays under its parent `write:exact-path/{canonical_repo_path}` family with exact owner lease resolved after E02 rebind. CAP-06 owns result/intake contract.

**Входы.** OPS-09 site-execution result/receipt and exact output digest; OPS-06 current grant for source/query/purpose/recipient/time; LIF-05 permitted copies, retention and sink decision; Institution’s observed site/network boundary and authorized recipient

**Выход и consumer.** Allowed or denied/limited release receipt bound to output digest and recipient, consumed by the authorized recipient and audit reader; no raw source copy is implied.

**Что можно готовить независимо.** Output interface can be prepared independently from site execution; actual output release joins its result, current grant and sink observation. Revocation/retry is rechecked at release.

**Где результат соединяется с другими.** Site worker evidence supports execution only. Source/use right, disclosure clearance, retention, population coverage and inference validity remain independent consumers; no encrypted marker grants access.

**Positive.** Cross-institution reviewer receives only permitted bounded result and bound receipt while raw data and secret paths stay local.

**Distinguishing negative.** Wrong recipient, revoked grant, retry after rights change, unauthorized temp/cache/backup copy or unapproved transfer blocks release and leaves a scoped result/limited outcome.

**Matched removal.** Remove recipient/sink check or local-copy evidence but retain network/deployment markers; actual selected output sink violates policy and the reader refuses.

**Граница контекста.** Authority boundary home G06; institution owns local security. This release card does not add raw-data custody service or a parallel disclosure ledger. P05/P09/P31/P32 require real sink-time decisions.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Selected tier is rebound to accepted E02 source; conditional selection remains the parent override.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-05](../../parents/OPS-05.md) | `direct:owner_readiness`: Consume selected retained-state/receipt and restore evidence only for the activated site workflow.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Current source/query authority is consumed before run and at actual recipient release; it is not supplied by credentials or network policy.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [CAP-06](../../parents/CAP-06.md) | `direct:owner_readiness`: CAP-06 owns private/federated input/result intake, roster and output-right handshake; OPS-09 only executes the selected site path.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-09.site-execution](../../cards/OPS-09/site-execution.md) | Only for the selected same-scope composition described by this card: Site worker evidence supports execution only. Source/use right, disclosure clearance, retention, population coverage and inference validity remain independent consumers; no encrypted marker grants access. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-09`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for output-release; selectors solution.migration_and_rollback, solution.composition_contracts[0], solution.composition_contracts[1] remain load-bearing.
  `solution.migration_and_rollback`; `solution.composition_contracts[0]`; `solution.composition_contracts[1]`
- **execute** — Direct result/preferred path for output-release; selectors solution.preferred_solution, solution.implementation_steps[3] name the work and native owner seam.
  `solution.preferred_solution`; `solution.implementation_steps[3]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for output-release; selectors task.r19_extension.question_slices[0], solution.acceptance_discriminators[0], solution.acceptance_discriminators[1] are checked at its actual reader/sink. Bundled subclauses: U050:{"question_id":"R18-D18-Q04","solution_ref":"solutions/lifecycle-r19/S15.md#r18-d18-q04","mechanism_ids":["S15-M2","S15-M3"],"role":"consumer"}.
  `task.r19_extension.question_slices[0]`; `solution.acceptance_discriminators[0]`; `solution.acceptance_discriminators[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
