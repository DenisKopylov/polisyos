# Допуск, события, права и операции: предпочтительные решения

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="LIF-01"></a>

## LIF-01 — Bind relation evidence to a specific admissible use

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-01]`. Review: [root-review](root-review.md#LIF-01).

### Предпочтительное решение

Extend existing Claim support, domain verification and Claim Ledger consumption. Resolve the exact permitted representation and selected profile before admission: retained bytes where lawful, or the permitted query/result receipt verified against its actual custodian-side execution and content/operation binding. A digest alone cannot replace unavailable content, and query-only limits on replay remain explicit. Keep assertion, assessment and use distinguishable: assertion binds exact occurrences/propositions; assessment records the predicate/method/rule and limitations; use binds the assessment to claim, estimand, purpose, audience, frozen basis and dependencies. Check polarity, population, unit, scope, effective-time role, translation occurrence, selection trace and any claimed independence at the existing consumer. Reassess changed purpose/audience. Same-code replay establishes consistency only; independent correctness evidence is required only where the selected claim or method asserts it, not as a universal verifier tax. Search no-hit is not absence and anonymous occurrences gain no invented identity.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/validation/claim_support.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `_satisfied_predicates`. Selected predicates can be satisfied by non-empty refs/strings: form proxy to replace for admitted predicates, not a finding about every caller.
- `policy-engine/src/polisyos/scientist/evidence/claims/models.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ClaimRecord`. Existing claim already binds claim_use, evidence ArtifactRefs, support and publishability.
- `policy-engine/src/polisyos/data_forge/domains/legal/source_relation.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `require_legal_source_relation_verification`. Typed verification_missing refusal is the current fail-closed legal disposition.
- `policy-engine/src/polisyos/core/artifacts/manifest.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ArtifactRef, ArtifactManifest.inputs`. Artifact ref/profile and lineage input already preserve exact selected artifact view.
- `policy-engine/src/polisyos/scientist/evidence/claims/head_index.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ClaimLedgerOwnerPort`. Canonical candidate persistence and current-head resolution already have an owner.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Resolve the selected retained ArtifactRef/profile or lawful query/result receipt and verify its native content/operation binding. Missing required evidence refuses authority; absence of prohibited raw retention is not itself a failure of a receipt-based contract. Preserve replay limitations.
2. Have the domain verifier emit immutable predicate, exact inputs, rule/method version, verifier provenance, time roles, result and limitation. Keep integrity, applicability, entailment, causal validity and authority separate.
3. Bind assessment to one ClaimRecord/use and frozen denominator; persist lifecycle change through the existing claim owner and expose it through the selected API/audit surface.
4. Rebind legacy records by exact content and intended use; unresolved records remain candidate/unknown.

### Рассмотренные альтернативы

- **Use references, hashes or PROV-O structure as relation proof** — Provenance describes who/what/when; it does not prove semantics or admit a purpose-specific use.
- **One universal verifier or mandatory independence check for every artifact** — Duplicates domain semantics and overstates independence for routine replay. Check only the claim predicate and authority band actually asserted.
- **Producer assertion promotes the claim** — Allows a source or LLM to supply its own authority and bypass the canonical consumer.

### Free-grow и ресурсы

- **data or config growth:** Versioned relation/source profiles and purpose/audience bindings are discovered and executed through existing domain/claim registries, without per-profile hardcoded caller dispatch.
- **extension boundary:** New conforming profiles are discoverable/executable without central-code or hardcoded fallback; genuinely new semantic predicates require a typed owner verifier, not arbitrary authority-bearing rules.
- **resource behavior:** Use existing per-run limits; exhaustion leaves candidate/limited and never silently truncates a denominator.


### Миграция и восстановление

Rebind historical records by exact content/profile. Suspend only the affected use and preserve the prior head plus refusal/limitation; retain history only under LIF-05 rights. Never auto-upgrade or restore authority over a later correction.


### Композиция и owners

- CAP supplies exact receipt/profile/bytes; domain owner supplies relation assessment; Claim Ledger owns use, head and projection.
- Classify gate predicates: content/rule checks may be recomputed; legal act/applicability is institutionally supplied; unknown scope remains candidate.
- Expose the selected use and audience without a universal metadata envelope.


### Acceptance и различающие проверки

- Positive: verified receipt supports one persisted use visible to a fresh consumer; changed purpose/audience is reassessed.
- Negative: wrong polarity/unit/population/scope, unbound translation, no-hit as absence, repeated cohort as independent, anonymous occurrence with invented identity.
- Removal: remove content resolution but keep refs/labels; reject. Remove purpose binding but keep assessment; changed-use reuse refuses or reassesses.


### Входы и ответственность за их получение

- CAP-02 exact receipt and retained ArtifactRef/profile.
- Domain method/rule and version; legal issuer provides act/jurisdiction/effective facts where applicable.
- Claim owner supplies claim, use, audience and public/audit surface.


### Когда обоснованно отклониться

- If existing consumer can bind exact content/use, extend it without a new record type.
- If predicate cannot be constructed or only search-hit evidence exists, keep candidate/limited pending a verifier receipt.
- New authority semantics require typed owner extension before publication.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O represents entities, activities, agents, derivation, invalidation and qualified roles, and allows application-specific specialization. **Граница:** It records provenance structure; it does not establish relation truth, method validity, independence or admissibility.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-02"></a>

## LIF-02 — Enroll source dependencies and fence currentness at publication

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-02]`. Review: [root-review](root-review.md#LIF-02).

### Предпочтительное решение

Extend source-event and Claim/Decision Validity owners with source cut C, enrollment high-water W and replay floor. Where source and dependency share one transaction owner, record edge/generation/outbox together. Otherwise evaluate at source-supported cut C, register exact scope and journal identity at W, then replay (C,W] before claiming currentness. Use source-native incarnation + partition + position, not wall time. Couple event receipt, dedupe, invalidation effect, append-only history and processed position in the consumer transaction. Publication compares expected claim head plus enrolled source/right cuts in a writer-participating transaction; if stores cannot share it, use prepare/reconcile or an explicitly scoped as-of cutoff with a verified source cut and native validity/expiry rule; signing the cutoff alone does not establish cross-store currentness. Mark coarse generation stale before delayed precise fanout. Missing replay floor/cut means stale/not_established.

### Что переиспользовать

- `policy-engine/src/polisyos/scientist/validation/decision_validity.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `record_dependency_event`. Static path saves dedupe before effect and skips missing dependencies, exposing event-before-enrollment gap.
- `policy-engine/src/polisyos/scientist/validation/decision_validity.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `read_current_projection, _overlay_epoch_pending`. Existing fresh-read and pending-epoch surface should consume currentness without a parallel projection.
- `policy-engine/src/polisyos/scientist/evidence/claims/lifecycle.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AppendOnlyClaimLedger, append_lifecycle_event`. Existing lifecycle history is the append-only reaction path.
- `policy-engine/src/polisyos/scientist/evidence/claims/head_index.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ClaimLedgerOwnerPort.resolve_current`. Current head resolution is owner controlled; fence at actual advance.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Bind evaluation to exact dependency scope and source cut C, journal identity, incarnation and supported continuity proof.
2. Enroll at high-water W and replay (C,W]; refuse when replay floor or cut mapping cannot be established.
3. Persist receipt, dedupe, invalidation, claim action and processed position together locally; use an outbox only for a local dual-write boundary.
4. Fence final public head on current source/right cut and expected head, or emit an explicit bounded cutoff; fresh reads surface pending reconciliation while scheduler is stopped.

### Рассмотренные альтернативы

- **TTL polling only** — Leaves a check/commit race and may stay green while the scheduler is down; acceptable only as an explicit candidate freshness bound.
- **Best-effort dual writes** — Crash between source and event creates a permanent gap; outbox must be atomic with its local owner.
- **Global source/claim/rights transaction or scheduler** — No shared transaction domain is established and a new service duplicates ownership without creating source evidence.

### Free-grow и ресурсы

- **data or config growth:** Source-native journal IDs, event scopes, cut mappings, replay floors and versioned dependency predicates are discovered/executed through source/claim registries without hardcoded per-source caller dispatch.
- **extension boundary:** New conforming source profile must be discoverable/executable and expose typed cut, event identity and continuity/replay rule; new semantics need an adapter, not central hardcoded fallback. Without these, use is limited to a declared as-of interval.
- **resource behavior:** Bound replay lag, retention and fanout by owner budgets; when floor is passed or storms exceed bounds, show stale and reconcile rather than drop events.


### Миграция и восстановление

Enroll old uses only from exact inputs and reconstructable cuts. Missing cuts/history remain not_established. Rollback suspends affected use, preserves append-only action and pending invalidation, and never restores prior authority.


### Композиция и owners

- CAP/source owns event and source cut; LIF consumes them.
- Claim owner atomically applies local receipt/dedupe/effect/head. Cross-store source/right commits require reconciliation or cutoff.
- Source completeness supplied by caller is consumer_asserted and cannot carry protected publication.


### Acceptance и различающие проверки

- Positive: before/after-enrollment changes invalidate a negative; unrelated generation does not; currentness is visible with scheduler stopped.
- Negative: pre-enrollment event, crash after dedupe, passed replay floor, lagging index, backdated event, coalesced revoke/restore and unchanged head with source drift.
- Removal: remove C-to-W replay or writer-participating fence while retaining markers; corresponding missed event/racing publication fails.


### Входы и ответственность за их получение

- Source owner: generation, snapshot cut, journal, replay floor, continuity, retention.
- CAP actual event receipt.
- Rights issuer supplies scoped act/effective time; publisher supplies actual head commit boundary.


### Когда обоснованно отклониться

- Use source-supported snapshot+log where available; without replay history require cutoff or re-evaluation.
- If publisher/source/right cannot share a transaction, agree prepare/reconcile or cutoff before edits.
- Keep coarse invalidation until a precise affected set is independently reconciled.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Logical Decoding Concepts, PostgreSQL 18](https://www.postgresql.org/docs/current/logicaldecoding-explanation.html) — A logical slot can pair an exported snapshot with a later ordered change stream; changes may replay after crash, consumers must handle duplicates, and slots retain WAL/catalog resources. **Граница:** Specific to PostgreSQL and its log scope; does not include external claim, rights or publisher stores.
- [Transaction Isolation, PostgreSQL 18](https://www.postgresql.org/docs/current/transaction-iso.html) — Serializable excludes transaction serialization anomalies; weaker Read Committed reads can see distinct snapshots across commands. **Граница:** Isolation covers only one database transaction.
- [Transactional outbox pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) — A local outbox transaction closes the database/event dual-write gap; relays may duplicate, so consumers must be idempotent and preserve needed order. **Граница:** Does not atomically commit downstream services or external effects.
- [Saga orchestration pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html) — Cross-store workflows use local transactions, forward recovery or compensation; participants need idempotency and the pattern is eventually consistent without isolation. **Граница:** Compensation is another act, not guaranteed rollback or global atomic commit.
- [Exactly-once source connectors, Apache Kafka Connect 4.2](https://kafka.apache.org/42/kafka-connect/connector-development-guide/) — Exactly-once source support requires meaningful source offsets and exact resume without loss or duplication; task generations can be fenced within Kafka Connect. **Граница:** Not a transaction across arbitrary external sources, claim ledger, CAS, rights and publisher.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-03"></a>

## LIF-03 — Fence capture frontier commits against stale writers

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-03]`. Review: [root-review](root-review.md#LIF-03).

### Предпочтительное решение

Extend Fabric CursorStore with an expected-prior-root and active-attempt fence at the final partition-head update. The inspected save path writes an artifact before locking and replaces the index without comparing prior head/fence, so lock serialization alone admits paused A after B. CAP remains the only capture producer. Bind cursor commit to source incarnation, selector/profile, partition, receipt, sealed root, native cut and current attempt epoch. Persist/verify permitted members and receipt first; then conditionally advance head/frontier in the cursor owner. Conflict keeps prior frontier and reconciles staged orphan bytes. Sparse positions are valid only under adapter continuity semantics. For HTTP resume, bind exact retained representation/profile and request variant; 304 cannot recreate a missing body, and ETag is not always a full content digest.

### Что переиспользовать

- `policy-engine/src/polisyos/fabric/data_plane/cursor_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CursorStore.save_partition_state`. Inspected index replacement has no expected-prior comparison or attempt fence at commit.
- `policy-engine/src/polisyos/core/contracts/cursor.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `PartitionCursorState`. Planning anchor says the checkpoint contract lacks typed attempt fence; rebind after E02.
- `policy-engine/src/polisyos/core/artifacts/manifest.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ArtifactRef, ArtifactManifest`. Immutable root/profile and exact inputs can bind receipt and members.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. CAP emits receipt bound to selector, adapter version, incarnation, source cut, coverage/filter and exact member refs.
2. Stage and verify immutable root plus receipt, then update head/frontier with expected-prior and active-fence comparison in one owner transaction or conditional write.
3. On crash/conflict, keep prior frontier; reconcile staged bytes against current head and receipt before GC.
4. Use strong If-Match/If-Range and matching request variant; absent exact 304 body refetches or stays unavailable.

### Рассмотренные альтернативы

- **File lock only** — Serializes writes but does not reject stale A after B; compare the expected root and active fence at commit.
- **Max offset or dense gap check** — Sparse/filter/opaque offsets make arithmetic density an invalid continuity proxy.
- **ETag as content hash** — S3 ETag is not always full-object MD5; CAS validator and independent content checksum are separate.
- **Kafka exactly-once as universal cursor contract** — Kafka source guarantee requires meaningful offsets and exact source resume within its connector scope.

### Free-grow и ресурсы

- **data or config growth:** Source profiles declare incarnation, partitioning, native order, sparse/filter semantics, range/page protocol, representation validator and receipt version.
- **extension boundary:** Discover and execute conforming typed adapters through CAP/Fabric registries without per-profile hardcoded dispatch; new transport/continuity semantics require a typed adapter and conformance.
- **resource behavior:** Bound staged bytes/orphans per accepted storage profile; exhaustion or incomplete receipt leaves prior frontier and partial/unavailable status.


### Миграция и восстановление

Legacy cursor rows without incarnation, expected head, attempt fence or verified receipt remain untrusted and need source-owner revalidation. Rollback preserves prior sealed root and conflict/orphan evidence; never reset nonempty frontier to empty/complete.


### Композиция и owners

- CAP owns capture/receipt; cursor owner owns commit fence and progress.
- Artifact owner supplies exact root/profile and durability; OPS supplies accepted persistence/backup assumptions.
- Expected-head is recomputed locally; source continuity is externally supplied evidence, not proved by cursor field shape.


### Acceptance и различающие проверки

- Positive: verified receipt advances one root once and fresh reader sees it after supported restart; legal sparse offsets work per adapter cut.
- Negative: A-after-B, crash between member/receipt/frontier, delete at snapshot boundary, incarnation ABA, missing child, 304 without body and sparse-vs-dense fixture.
- Removal: remove expected-root compare or representation binding but keep lock/ETag markers; stale writer or absent body must fail.


### Входы и ответственность за их получение

- CAP source cut/receipt and representation rules.
- Artifact owner read-back/durability.
- OPS persistence/backup topology.


### Когда обоснованно отклониться

- If blob and cursor cannot share a transaction, stage immutable root then reconcile before conditional head advance.
- If source cannot provide cut/continuity, allow only bounded partial/historical observation.
- If 304/range lacks exact representation binding, refetch or stay unavailable.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) — If-Match uses strong entity-tag comparison to prevent stale state-changing updates; If-Range resumes only on an exact strong validator match. **Граница:** A validator is an origin assertion, not independent completeness or byte-integrity evidence.
- [RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html) — 304 updates and reuses a suitable stored response selected by URI, request variant and validators. **Граница:** 304 has no replacement body; without the exact stored representation it cannot reconstruct a complete capture.
- [Conditional writes, Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html) — If-Match conditional writes fail when current ETag differs; concurrent writes/deletes can produce precondition, conflict or not-found outcomes. **Граница:** Protects one S3 object update, not another database head or semantic currentness.
- [Object API: ETag, Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html) — ETag is not necessarily a full-object MD5 for multipart uploads or some encryption modes. **Граница:** Conditional-write validator and independently computed content digest are different evidence.
- [Exactly-once source connectors, Apache Kafka Connect 4.2](https://kafka.apache.org/42/kafka-connect/connector-development-guide/) — Exactly-once source support requires meaningful source offsets and exact resume without loss or duplication; task generations can be fenced within Kafka Connect. **Граница:** Not a transaction across arbitrary external sources, claim ledger, CAS, rights and publisher.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-04"></a>

## LIF-04 — Preserve long-running duty across retry, cancel and uncertain effects

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-04]`. Review: [root-review](root-review.md#LIF-04).

### Предпочтительное решение

Extend the existing RuntimeOperationIntent/ControlPlaneStore path. Persist stable scoped effect identity and request digest before remote call; keep intent, attempts, provider observations and final local commit distinct. Reuse the same provider idempotency key only with exact request binding and within the provider’s documented retention/reconciliation window. Complete local result/event/outbox under the existing transaction and owner token. Cancellation races explicitly with provider acceptance and local publication; timeout, lease expiry and cancel request do not prove that the provider stopped. If response is lost or window uncertain, retain unknown/recovery_required and reconcile by provider receipt/status before retry. Recheck actor authority before resumed sensitive action; keep long-lived duty on authorized service identity with visible transfer/cutoff.

### Что переиспользовать

- `policy-engine/src/polisyos/runtime/http/services/run_operation_idempotency.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RuntimeOperationIntentStatus, RuntimeOperationIntentKey, RuntimeOperationIntentStore`. Typed local status already includes unknown/pending/completed/refused/recovery_required and disclaims external exactly-once.
- `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `begin_runtime_operation_intent, complete_runtime_operation_intent_with_observation, require_runtime_operation_recovery`. Existing local transaction and recovery seam can own the bridge.
- `policy-engine/src/polisyos/runtime/http/services/control_worker.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlWorker.dispatch_once`. Existing worker is the dispatch boundary; rebind lease/cancel semantics.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Persist scoped intent, actor, exact request digest, provider operation identity, duty owner and bounded attempt policy before dispatch.
2. Record each provider attempt and receipt/nonreceipt; use existing local outbox/control-plane transaction.
3. Reconcile provider status before atomically persisting effect observation, final job/claim result and lifecycle event.
4. Expose unknown separately; transfer or retire duty through OPS-authorized successor/cutoff.

### Рассмотренные альтернативы

- **Add Temporal as a second scheduler/status plane** — It illustrates retries and heartbeat cancellation, but existing ControlPlaneStore is the canonical local intent owner.
- **Idempotency key means indefinite exactly-once** — Provider windows differ; Stripe v1 may prune after 24 hours and then reuse starts a new request.
- **Saga compensation means remote rollback** — Compensation is another act; saga is eventually consistent and cannot erase irreversible disclosure.

### Free-grow и ресурсы

- **data or config growth:** Purpose-specific effect profiles, provider idempotency windows, receipts, reconciliation methods, quota/backoff and duty-transfer rules are discovered/executed through current registries without per-provider hardcoded caller dispatch.
- **extension boundary:** New conforming effect profiles are discoverable/executable without central-code fallback; new protocol semantics require a typed adapter for identity, request binding, receipt/status and cancellation behavior.
- **resource behavior:** Respect account/method quotas, cooldown and attempt bounds; exhausted or uncertain work remains recovery_required without busy retries.


### Миграция и восстановление

Reconcile legacy pending/completed rows against provider receipt and request digest. Missing identity or expired window stays unknown for bounded external resolution. Rollback only unpublished local state; preserve attempt/duty history as rights allow and never report a remote effect undone.


### Композиция и owners

- ControlPlaneStore owns local intent/attempt/result/outbox; do not create a second scheduler.
- Provider receipt/window/quota is institutionally supplied evidence.
- OPS supplies service identity and continuity; actor grants are rechecked before sensitive resume.


### Acceptance и различающие проверки

- Positive: known provider effect becomes one reconciled local effect/final result; retry within real provider window preserves identity.
- Negative: accepted effect/lost reply after key expiry, cancel before/after acceptance, old worker after lease, 429, store outage, compacted history and wrong issuer receipt.
- Removal: remove outcome reconciliation but keep key; blind repeat fails. Remove cancel/final fence but keep marker; accepted effect cannot report stopped.


### Входы и ответственность за их получение

- Provider API contract and queryable receipt/window.
- OPS authorized worker identity, successor and cutoff.
- Caller grants and current rights generation.


### Когда обоснованно отклониться

- Queryable durable provider operation ID: reconcile it; no reliable receipt/query: retain unknown.
- If already accepted E02 provides complete outcome inbox, consume it instead of duplicating.
- Irreversible effect gets local-only rollback plus bounded public limitation.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Transactional outbox pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) — A local outbox transaction closes the database/event dual-write gap; relays may duplicate, so consumers must be idempotent and preserve needed order. **Граница:** Does not atomically commit downstream services or external effects.
- [Saga orchestration pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html) — Cross-store workflows use local transactions, forward recovery or compensation; participants need idempotency and the pattern is eventually consistent without isolation. **Граница:** Compensation is another act, not guaranteed rollback or global atomic commit.
- [Detecting Activity failures, Temporal](https://docs.temporal.io/encyclopedia/detecting-activity-failures) — Retries create another attempt; heartbeat payload can resume progress and cancellation is delivered through heartbeat processing. **Граница:** Timeout/cancellation does not prove a provider-side operation stopped.
- [Idempotent requests, Stripe API](https://docs.stripe.com/api/idempotent_requests) — Stripe API v1 saves first response after execution begins, compares request parameters, and may prune keys after at least 24 hours; reuse after pruning starts a new call. **Граница:** Provider- and API-version-specific; does not prove a remote effect after lost reply.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="LIF-05"></a>

## LIF-05 — Fence rights-sensitive materialization, deletion and restore

Исходная запись: [tasks.json](../tasks.json), `tasks[id=LIF-05]`. Review: [root-review](root-review.md#LIF-05).

### Предпочтительное решение

LIF-05 owns the single source-use/AP07 decision and composition seam consumed by CAP-03/06. At accepted-source rebind, bind competent external rights evidence/verifier, native source-use decision owner, placement/write/delete/restore owners and retention planner separately. Reuse a proved decision owner; if absent, extend the canonical core/security source-use boundary once under LIF-05, with typed contract, producer, consumer and public companions. This is internal engineering, not an external wait. Do not derive grant authority from AccessScope or RetentionPlanner. AccessScope is request identity/authz scope; RetentionPlanner plans policy/impact and does not prove grants or purge. Consume a scoped rights decision carrying authority, provenance, effective time, rule version, purpose/audience and generation. Enroll writes/disclosures before materialization, stage bytes unservable, and publish only if the rights generation still matches at the actual write/head fence. Revoke during staging blocks publication; disclosed bytes cannot be recalled. Pin/drain active readers where supported. Record deletion outcome per actual managed placement and distinguish membership unlink, managed-byte deletion, backup status and external/provider copies. Restore into quarantine and replay post-backup rights/retention history before serving. CAP-03/06 consume this same rights/privacy owner for protected-unit aliases/overlap and disclosure composition; unknown overlap is not disjoint and unknown output holds reservation.

### Что переиспользовать

- `policy-engine/src/polisyos/core/security/access_scope.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AccessScope`. Per-request tenant/cell/principal/roles scope is not source-specific lawful-use authority.
- `policy-engine/src/polisyos/fabric/security/retention.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RetentionPlanner, RetentionPolicy, SnapshotDeletionImpact`. Existing plan/impact seam is not actual placement purge or restore proof.
- `policy-engine/src/polisyos/core/artifacts/manifest.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ArtifactRef, ArtifactManifest, InputRef`. Existing exact artifact and parent/profile identities can bind placement/restore receipts.
- `policy-engine/src/polisyos/core/artifacts/store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `open_member, open_member_bounded`. Existing read boundary must be rebound for actual placements and active pins.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Rights owner resolves actual grant/revoke/hold, use, audience, scope, effective time and generation; AP07 unit/alias/recipient composition is the same owner used by CAP-03/06.
2. Reserve write/disclosure intent before bytes. Stage unservable and recheck generation at final root commit; otherwise keep quarantined and reconcile.
3. Enumerate actual CAS/version/cache/temp/log/export/provider/backup placements and reader pins; persist per-placement outcome and exact exclusions.
4. Restore quarantine replays post-backup rights events and roots. Unknown history or placement blocks serving; disclosure timeout after possible output is indeterminate and not refunded.
5. Record one canonical decision API and consumer census for CAP-03/06; absent decision/composition is absent/unallocated or bridge_missing to implement in this task. Distinct competent authority, verification, placement and retention responsibilities remain explicit; one seam does not make one institution sovereign over all sources.

### Рассмотренные альтернативы

- **Tombstone or impact plan proves all-copy deletion** — S3 versioning illustrates that delete marker hides bytes while older versions remain retrievable.
- **Universal crypto-shred** — Requires complete copy/key/backup/shared-object and active-reader inventory; otherwise exceeds custody.
- **New global rights or privacy-budget registry** — Splits the existing rights/privacy owner and CAP-03/06 consumers.
- **Restore then apply tombstone asynchronously** — Creates a serve window and can miss expired post-backup history.

### Free-grow и ресурсы

- **data or config growth:** Custodian-defined grants, retention, protected units, aliases, recipient and composition profiles are discovered/executed through current rights/artifact registries without per-profile hardcoded dispatch.
- **extension boundary:** Conforming profiles are discoverable/enforceable through the existing rights/artifact registries, without per-profile hardcoded dispatch; new law/privacy semantics/storage placement needs an authorized decision and typed adapter.
- **resource behavior:** Use existing budgets for placements, pins, restore lag and disclosure reservations. Unknown overlap/inventory blocks protected action; no invented global deletion/privacy number.


### Миграция и восстановление

Inventory actual placements and post-backup rights history. Unindexed/foreign placements remain unresolved, not deleted. Suspend sensitive writes and quarantine roots; preserve only history allowed by the authorized retention decision, minimize restricted content as required, and never claim recall of already disclosed bytes or restore old rights over newer revoke.


### Композиция и owners

- One canonical rights/privacy owner emits decision/generation/composition; CAP-03/06 consume it.
- Artifact/CAS owner owns write/head/delete/pins/restore; OPS supplies backup topology.
- External legal act, provider and backup receipts are typed evidence with bounded custody; unqualified all-copy claims require independently reconciled inventory.


### Acceptance и различающие проверки

- Positive: exact authorized purpose/audience admits write; restore with post-backup revoke remains blocked until reconcile; authorized sharing passes.
- Negative: revoke between check/commit and during stream, CAS/WORM/backup copies, active reader, stale restore, missed expiry, coalesced revoke/restore, overlapping releases and lost output.
- Removal: removing write fence, restore replay, placement reconciliation or shared reserve/indeterminate hold while markers remain makes the corresponding semantic gate fail.
- A retention default or request AccessScope without verified source-use grounds cannot become a grant; a lawful source-use decision passes without a second private rights ledger.


### Входы и ответственность за их получение

- Competent rights authority supplies applicable grant/revoke/retention and effective time.
- Artifact/CAS/provider/backup owners provide actual placements, pins, receipts and restore topology.
- CAP-03/06 supply selected query outputs, recipients, source-defined units and composition law.


### Когда обоснованно отклониться

- External placement or incomplete inventory means exact unresolved scope, never all-copy claim.
- If lawful retention applies, preserve only within that decision/safeguards; if erasure applies, report placement-specific outcomes.
- No atomic rights/write boundary: keep staged bytes quarantined until prepare/reconcile/cutoff.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Retaining multiple versions of objects with S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html) — Normal delete inserts a current marker and leaves older versions retrievable; permanent removal requires version-specific delete and lifecycle handling. **Граница:** Shows one S3 bucket behavior, not PolicyOS or every store.
- [Locking objects with Object Lock, Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html) — Retention/legal hold applies to specified object versions; compliance mode can prevent deletion during retention and governance mode has authorized bypass. **Граница:** Storage control is not a legal applicability decision or complete copy inventory.
- [Regulation (EU) 2016/679, Articles 17 and 89](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679) — Erasure is tied to specified grounds and exceptions include legal obligation and qualifying public-interest archiving/research with Article 89 safeguards; Article 17(2) addresses reasonable steps to inform other controllers. **Граница:** Applicability depends on facts, role, jurisdiction and other law; PolicyOS consumes the competent decision.
- [Transactional outbox pattern, AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) — A local outbox transaction closes the database/event dual-write gap; relays may duplicate, so consumers must be idempotent and preserve needed order. **Граница:** Does not atomically commit downstream services or external effects.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
