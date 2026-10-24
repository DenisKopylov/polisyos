# OPS-12.offline-restore — Сверять offline restore до protected use

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-12](../../parents/OPS-12.md). Роль: `consumer`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** A selected offline restore admits protected reads only when local bundle/runtime/DB/CAS, rights, trust generation and as-of/anti-rollback state reconcile for the fresh local reader.

**Предпочтительное решение.** Reuse OPS-05 restore-to-reader join and existing local runtime-state/CAS migration owners. Import to quarantine, reconcile rights/revocations absent from snapshot within declared offline basis, and report bounded historical/limited scope if freshness cannot be established.

**Граница владельца.** OPS-12 parent `write:exact-path/{canonical_repo_path}` and selected local restore resource family are resolved after E02; OPS-05/DB/CAS owner write leases remain canonical. No separate offline recovery engine or new scheduler.

**Входы.** OPS-05 selected local DB/CAS restore cut and fresh-reader witness; Bundle-currentness local import/generation/as-of result; OPS-06 source-use grant and LIF-05 actual rights/retention history; OPS-11 trust succession evidence; Institution local identity/model/source/secret and operator succession inputs

**Выход и consumer.** Quarantined local restore receipt and supported/limited fresh-reader outcome on the selected bundle generation; actual selected consumer cannot use un-reconciled state.

**Что можно готовить независимо.** Restore workflow can prepare against OPS-05’s agreed interface. Composition is required only for selected offline tier and affected protected read; old snapshot cannot be treated as current merely because offline.

**Где результат соединяется с другими.** Joins OPS-05 physical restore and history, OPS-11 trust, OPS-06 grant and local bundle-currentness. No cloud/API status is a substitute; no-egress is a separate boundary proof.

**Positive.** Authorized local bundle/state imports, trust generation and explicit as-of permit the declared offline historical scope; supported restore is measured to a fresh protected read.

**Distinguishing negative.** Clock rollback, replayed old rights, missing model/method, expired grant, unsigned successor or stale snapshot keeps affected protected scope quarantined/limited; independent scopes remain eligible.

**Matched removal.** Remove local rights/history/generation/restore reconciliation but keep bundle/restore markers; fresh local reader refuses unsupported currentness.

**Граница контекста.** Conditional offline composition is not complete recovery or cloud parity. The existing OPS-05 restore writer and local institution identity/operators remain owners; P05/P07/P08/P37/P38 bind time and source limits.

## Место в цепочке

| Отношение | Точный смысл |
|---|---|
| Supplier [P0-ACCEPT.accepted-boundary](../../cards/P0-ACCEPT/accepted-boundary.md) | `direct:actual_E02_G_acceptance`: Accepted-source rebind and conditional profile choice remain parent stage conditions; local profile can proceed without cloud-profile completion.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-05](../../parents/OPS-05.md) | `direct:owner_readiness`: Consume exact selected local restore-to-reader and history reconciliation; offline slice is not a standalone recovery system.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-06](../../parents/OPS-06.md) | `direct:owner_readiness`: Consume current source-use rights at local protected read; no-egress or signature does not grant use.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Supplier [OPS-11](../../parents/OPS-11.md) | `direct:owner_readiness`: Consume independently authorized technical trust generation/succession only for selected offline operation.<br>Выбор output: Select the exact output named in need and its original conditions, not all supplier cards. Actual source-qualified artifacts are pinned at dispatch/composition.<br>Условия: original direct relation; source stage rules govern |
| Composition output (не start gate) [OPS-12.bundle-currentness](../../cards/OPS-12/bundle-currentness.md) | Only for the selected same-scope composition described by this card: Joins OPS-05 physical restore and history, OPS-11 trust, OPS-06 grant and local bundle-currentness. No cloud/API status is a substitute; no-egress is a separate boundary proof. Independent output production/preparation remains allowed; the original parent join reconciles all required outcomes without making this list an all-of. |
| Composition output (не start gate) [OPS-12.no-egress](../../cards/OPS-12/no-egress.md) | Only if the selected offline protected-read/restore profile makes the no-egress claim; use actual independent observation, never a universal prerequisite for unrelated local use. |

Отсутствие внутреннего after не отменяет parent prerequisites. Conditional acceptance, execution rights и выбранные profiles разрешаются отдельно, как указано в parent contract. Номера групп и карточек не задают порядок.

## Назначенный нормативный контекст

Основа: `ec3d7d38b4d246b3e1d225a1c0fc9aefae9ced0d`. Полные selectors и accountable routes — [coverage.json](../../coverage.json), parent `OPS-12`. Эти ссылки не требуют чтения всех siblings. Читайте целиком каждый назначенный fragment и необходимые связанные contracts; mixed clause нельзя усечь до удобной части.

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for offline-restore; selectors task.r17_extension.delivery_slices[1] remain load-bearing.
  `task.r17_extension.delivery_slices[1]`
- **execute** — Direct result/preferred path for offline-restore; selectors solution.implementation_steps[2] name the work and native owner seam.
  `solution.implementation_steps[2]`
- **join** — Distinguishing behavior, consumer surface, or acceptance evidence for offline-restore; selectors task.r17_extension.quality_cases[1], task.r19_extension.question_slices[1] are checked at its actual reader/sink. Bundled subclauses: U032:{"question_id":"R18-D16-Q02","solution_ref":"solutions/lifecycle-r19/S16.md#r18-d16-q02","mechanism_ids":["S16-M2"],"role":"input collection"}.
  `task.r17_extension.quality_cases[1]`; `task.r19_extension.question_slices[1]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
