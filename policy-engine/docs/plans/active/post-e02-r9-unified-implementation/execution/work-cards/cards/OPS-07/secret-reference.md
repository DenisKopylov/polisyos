# OPS-07.secret-reference — Разрешать секрет непосредственно перед вызовом

Группа: [G09 — Развёртывание, исполнители, хранилища и ресурсы](../../groups/G09.md). Родитель: [OPS-07](../../parents/OPS-07.md). Роль: `mechanism`.

Плановая рабочая карточка. Реализация только после E02 acceptance и exact source/lease rebind; эта запись не является execution grant или closure. [Общие правила](../../README.md).

**Проверяемый результат.** Only a current purpose/source/recipient-scoped secret reference resolves to an ephemeral connector credential at execution; secret values never enter job payload, log, receipt or projection.

**Предпочтительное решение.** Resolve an institution/external-issued secret reference just before the call through its actual issuer. For PolicyOS connector/workload credentials, reuse the existing deployment/config owner and its rotation/revocation path. Recheck grant and credential generation on retry/resume; redact values at every output.

**Граница владельца.** Any write stays with the canonical connector/config or worker owner under OPS-07’s native lease family `write:exact-path/{canonical_repo_path}`; exact paths and overlaps remain unestablished until E02 rebind and are not presumed disjoint. The existing deployment/config owner owns technical credential storage, rotation and revocation; an institution/external issuer supplies those facts for secrets it issues. OPS-06 owns permission; this card creates neither credential authority nor permission.

**Входы.** OPS-06 resolved source/use grant; OPS-04/LIF-04 durable attempt identity and retry/resume; Credential reference, generation and revocation evidence from the existing deployment/config owner or, where applicable, the actual institution/external issuer

**Выход и consumer.** Ephemeral credential handle for connector execution plus reference-health receipt without the value, consumed by the connector and redacted operator surface.

**Что можно готовить независимо.** Prepare reference/schema and redaction paths after agreed secret issuer contract. Resolve only in worker just before effect; missing or expired issuer evidence holds that call, not unrelated work.

**Где результат соединяется с другими.** Permission, credential validity and provider billing authority remain separate; account budget card binds same attempt, but a secret is not permission or a spend cap.

**Positive.** Authorized call resolves the scoped reference at execution and no secret value appears in any persisted/projection surface.

**Distinguishing negative.** Expired/revoked grant, generation mismatch, connector switch, retry after timeout or broad secret scope refuses; no secret is copied into the job or log.

**Matched removal.** Remove resolution/redaction/recheck but retain credential-reference and quota fields; the behavioral secret-leak and stale-key tests fail.

**Граница контекста.** One secret-custody result under the existing connector/worker seam. Do not expose material through telemetry/cardinality overflow; P05/P15 and P31/P32 enforce actual boundary and authority.

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

- **binding** — Binding scope, authority, migration, time, input, or lifecycle constraint for secret-reference; selectors solution.deviation_triggers[1], solution.inputs_to_resolve[0] remain load-bearing.
  `solution.deviation_triggers[1]`; `solution.inputs_to_resolve[0]`
- **execute** — Direct result/preferred path for secret-reference; selectors solution.implementation_steps[0] name the work and native owner seam.
  `solution.implementation_steps[0]`

Inherited owner/lease/stage/activation constraints указаны в parent contract. Root/lead проверяет полное parent coverage; output этой карточки не закрывает siblings. При обнаружении пропуска остановить только affected writes/acceptance, назвать точный clause и reconciled next owner.

Product verification: **UNRUN**. Полные deciding outputs и fresh-consumer witness появятся при исполнении; markers или этот документ их не заменяют.
