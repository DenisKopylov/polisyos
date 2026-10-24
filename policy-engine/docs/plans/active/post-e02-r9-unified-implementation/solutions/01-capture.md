# Получение и поиск: предпочтительные решения

R15: для CAP-06 обязательны также `r15_extension` в [tasks.json](../tasks.json), [технический full-cycle](15-technical-method-lifecycle.md) и [joint-model research](../research/heterogeneous-model-execution.md). Исходные criteria ниже сохранены; additions не создают второго owner.

Статус: engineering recommendations; product execution UNRUN. Реализация только после E02 acceptance и полного affected-scope rebind. Исходные критерии не сокращаются; [общие решения](00-shared-decisions.md) предотвращают второго owner. [Нормативные уточнения](decision-clarifications.md) остаются предложениями.

<a id="CAP-01"></a>

## CAP-01 — Exact-source reconciliation and candidate discovery

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CAP-01]`. Review: [root-review](root-review.md#CAP-01).

### Предпочтительное решение

After A0 resolves the real current caller and source denominator, extend that acquisition route to compose the existing SemanticDatasetCatalog, SourceContract, planner, and source-specific connector. Discovery returns a persisted candidate/ambiguous/unavailable receipt bound to the exact source contract revision, profile, selector, requested time, and discovery method. Ranking and LLM/web results stay candidate state. Before a search provider call, bind the exact outbound query projection, purpose, sensitivity, provider/recipient, and allowed logging/retention to accountable source/custodian permission via its native verifier or another verified lawful basis applicable to the exact query/provider; a new custodian signature is not mandatory for demonstrably owned/public nonsensitive material. Unknown sensitivity or disclosure authority blocks egress or leaves that profile unclaimed. Preserve Rule 12's discoverable → executable → admitted separation; do not route from a hardcoded fallback or let page content expand tool rights.

### Что переиспользовать

- `policy-engine/src/polisyos/fabric/catalog/discovery.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `SemanticDatasetCatalog.refresh/search/resolve`. R9's pinned C inventory reports existing source-contract-backed search, resolution, ambiguity, and stale-entry behavior; ranking is not admission.
- `policy-engine/src/polisyos/fabric/connectors/contracts/source_contract.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `SourceContract`. R9's pinned C inventory reports source, security, terms, replay, lineage, trust, processing, retention, and versioned contract fields.
- `policy-engine/src/polisyos/runtime/quality/acquisition_planner.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `plan_evidence_acquisition/run_acquisition_closed_loop`. Existing gap planning and record/replay gateway are reported, but the generic planner-to-live producer-to-admitted reuse caller is not established.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. At A0, identify the real caller and enumerate its complete candidate/source denominator; rebind the proposed AcquisitionActionService path to the accepted E02 tree before writing.
2. Use the existing typed index and connector registry to search, resolve, or return ambiguity; persist a candidate receipt and forward only the selected exact contract/profile to its registered producer.
3. For selected web/LLM search, construct the minimum query locally, run owner-authorized disclosure admission on that exact projection and recipient, then egress; record only a permitted opaque receipt token or tenant-scoped keyed binding and decision; do not expose a guessable digest of a low-entropy protected query, and do not copy sensitive query text into logs.
4. Keep the receipt visible as candidate/ambiguous/not_admitted/resolved, then require the normal source-use verifier to emit the separate admitted-use receipt consumed by the route.

### Рассмотренные альтернативы

- **Autonomous LLM search over arbitrary URLs and caller-provided result text** — It collapses discovery into authority, permits URL/parser and tool-expansion attacks, and can disclose protected context to an unapproved search recipient.
- **Add a second global source registry or discovery service** — SourceContract and catalog/connector indexes already own discoverability; a parallel index would drift and create P27 owner bypass.

### Free-grow и ресурсы

- **data or config growth:** A correctly implemented source in an already supported protocol class becomes discoverable by adding a typed source contract/profile and registry entry, with zero central routing changes; candidate visibility does not imply executable or admitted authority.
- **extension boundary:** A genuinely new protocol/semantic class needs a reviewed typed connector/adapter plus conformance admission, registered for discovery. No arbitrary fetched code, model text, or fallback list becomes executable.
- **resource behavior:** Bound candidate count, query bytes, request timeout and search work by selected profile limits. Truncation or poor recall yields partial/ambiguous/unavailable with the index generation and cutoff, never a silent no-hit-as-absence result.


### Миграция и восстановление

Re-resolve legacy URLs/model outputs against the selected owner; never backfill identity, license, permission, or source authority from them. On discrepancy, disable the bridge, preserve candidate/audit history within retention rights, and mark the source/use unresolved; do not restore authority over a later revocation.


### Композиция и owners

- Bind the exact query projection, candidate, purpose, sensitivity, recipient and logging/retention to its verified disclosure basis before requesting. Expose only a permitted scoped keyed MAC or opaque protected reference; no unkeyed low-entropy public digest and no reference disclosure when the source forbids it.
- Discovery is a candidate producer. The separate LIF-01/native verifier decides whether the exact source artifact may support a specified use; ODRL-like policy syntax may be an input format but not proof of the policy author's authority.
- Source content and instructions are untrusted data; source discovery cannot alter connector registry, network egress, permissions, or tool set.


### Acceptance и различающие проверки

- Positive: an exact minimally disclosed query passes native recipient/purpose/rights admission and reaches only the admitted search provider; an allowed source candidate then takes the existing capture/admission path.
- No-hit: the admitted search request may execute to establish zero hits; persist its permitted no-hit receipt and perform no subsequent candidate/source fetch or admitted use. Refused disclosure means no protected query reaches the provider or its logs.
- Adversarial: withheld approval, unknown sensitivity/recipient, prompt injection, substituted source, provider-log leak or unkeyed guessable public query digest cannot authorize egress/use. Test an allowed public-query contract as well as a separately required custodian grant, without inventing a universal conjunction.
- Removal: delete actual pre-egress disclosure/recipient verification but keep permission markers; the negative reaches the transport and the semantic gate must fail.


### Входы и ответственность за их получение

- A0's complete source denominator, the actual caller and registry/connector owner in the accepted E02 tree.
- Native-verifier evidence that the selected provider/source/use contract authorizes the exact disclosed query OR applicable accountable custodian permission. Independently applicable provider logging/retention/training/region/recipient constraints still apply; no unrelated custodian grant is required for every lawful public/owned nonsensitive query.
- Source-specific contract evidence and verifier provenance for permitted use; if absent, deny the query or mark the profile unclaimed.


### Когда обоснованно отклониться

- If A0 cannot identify a served caller or an owner for query disclosure, do not build another service; record `bridge_missing`/`not_established` and retain only non-egress candidate discovery.
- If a new search/transport semantic class requires executable behavior, add a typed adapter and conformance path, then prove registry discovery works with no central fallback.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [OWASP Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) — For known destinations, accept a host from an allowlist and construct the request locally; validate resolved IPv4 and IPv6 targets and bind the connection to an approved address because a separate DNS check does not prevent rebinding; redirects and parser disagreement must not bypass destination checks. **Граница:** This is defensive guidance, not a proof of the repository's proxy, DNS, socket, or firewall behavior; those enforcement points must be verified for the selected deployment.
- [ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/) — ODRL supplies an interoperable model for asset-linked permissions, prohibitions, duties, parties, and constraints, useful as an input vocabulary for purpose/use evidence. **Граница:** An ODRL expression can state a policy but does not authenticate its issuer, establish signer competence, decide legal force, or prove that a custodian granted the asserted permission.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O separates entities, activities, and agents and connects used/generated entities with responsible agents and times, a useful reference for capture and transformation provenance. **Граница:** A provenance graph records asserted relationships; it does not make an agent's assertion true or supply authority, permission, or verification.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CAP-02"></a>

## CAP-02 — Safe capture, complete immutable snapshot and exact reuse

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CAP-02]`. Review: [root-review](root-review.md#CAP-02).

### Предпочтительное решение

Extend the selected Fabric HTTP connector to capture one bounded response as an immutable body-plus-request/response witness when the selected profile permits raw retention; otherwise use CAP-03’s lawful query/result-receipt boundary under the exact source profile, then make later readers resolve that exact root through ArtifactRef/manifest and current admission. Treat an ETag as an opaque representation validator, not the body's hash. A 304 is usable only when the matching stored body is readable and its target, representation profile, Vary dimensions, source identity, and permission still resolve; otherwise return unavailable. Retain the bounded WDI single-response route as the original A1 witness, not a system-wide transport or scheduling restriction. Prepare disjoint selected file/query/stream/paged adapters in parallel against their exact interfaces; each activates only after its own required conformance, rights and resource checks. Pagination, delta, ranges, or competing cursor writers activate only with source-native completeness/cut evidence and LIF-03's conditional receipt-before-frontier commit; CAP does not add a second cursor writer.


### Что переиспользовать

- `policy-engine/src/polisyos/fabric/connectors/sources/http_base.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `RawHTTPResponseObserver`. Pinned C inventory reports bounded body hooks and original-request observation, but not per-hop redirect authorization.
- `policy-engine/src/polisyos/fabric/connectors/reference/static_csv.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `StaticCSVConnector.fetch (304 branch)`. At C, the 304 branch returns an empty DataFrame/row_count 0 and not_modified metadata; RFC semantics and the source inventory show no prior-body binding there.
- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `execute_live_catalog_acquisition`. Pinned C inventory reports an intentionally narrow, bounded one-page WDI producer that refuses more-than-one-page behavior.
- `policy-engine/src/polisyos/fabric/data_plane/cursor_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CursorStore.save_partition_state`. Pinned C inventory reports a serializing writer without an expected-head/attempt compare-and-commit fence; LIF-03 is assigned that owner.
- `policy-engine/src/polisyos/core/artifacts/manifest.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ArtifactManifest/ArtifactRef`. Pinned C inventory reports immutable content/provenance/authority manifest identity; this is identity plumbing, not permission.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Use a contract-owned endpoint/profile, not a page-supplied URL. For each hop, validate scheme/host/port, resolve and bind approved IPv4/IPv6 addresses at connect time, recheck redirects, constrain proxy and origin-scoped credentials, and enforce deployment egress policy.
2. Before capture can write any body/temp/log/cache, obtain LIF-05/native source-use permission for that actual placement. Record only permitted request/hop/status/media/encoding/Vary/validator/size/time details. In a retention-permitted profile persist the exact bounded body before exposing its durable receipt. In query-only mode retain only permitted output/receipt and never stage forbidden raw bytes; unavailable raw replay remains a limitation. CAP-03 later reuse admission cannot retroactively authorize capture storage.
3. For 304, resolve the exact retained representation matching request key and source profile and update only permitted metadata. For range, require strong If-Range validator, valid Content-Range, gap-free nonoverlapping assembly, and whole-body digest; a 200 response replaces the partial path.
4. For pagination, accept a provider's opaque continuation/snapshot token only within the admitted source/query and independently authorized recipient set; a provider CDN or foreign-origin continuation needs its own exact egress/credential scope rather than blanket same-origin acceptance or prohibition. Persist each page receipt; commit the final cut through LIF-03's expected-head/attempt fence.
5. Treat a byte-identical retried page under the same source-defined token/cut idempotently; conflicting contents, skipped required coverage or unbound continuation remain partial/refused. Allocate the actual second-source capture/parser/protocol sub-slice required by LIF-08; first-route completion cannot substitute for it.
6. For a selected controlled-proxy route, verify an authenticated request-bound enforcement result binding the exact request/attempt, resolved final target, proxy/policy identity and actual egress decision, including redirected hops and credential audience. A client socket peer that is merely the proxy, a forwarding header or proxy configuration is not target evidence. Use the existing transport/security seam; missing or mismatched required evidence refuses that destination/use. Private targets may pass only under the expressly permitted private-connector profile, never public-discovery privilege.


### Рассмотренные альтернативы

- **Treat 304 as an empty dataset or reconstruct from ETag alone** — RFC 9110 defines 304 as no representation body and RFC 9111 reuses a matching stored response; without that body, the capture is unavailable.
- **Enable generic pagination/range based on Link or max offset** — Link does not prove a stable snapshot; range support is optional and validators can change. A protocol-specific completeness receipt and LIF-03 fence are required.
- **Add a second cursor/frontier store in CAP** — LIF-03 owns expected-head, attempt fencing, crash recovery, and receipt-before-frontier ordering.


### Free-grow и ресурсы

- **data or config growth:** New endpoints already using the admitted HTTP semantics are discovered through typed source contracts/profiles and the existing connector registry, without central capability lists.
- **extension boundary:** New pagination, range, streaming, or source-cut semantics need a typed connector extension and conformance evidence; the capability is not enabled by setting a marker or following arbitrary response links.
- **resource behavior:** Apply source-profile caps to redirect hops, pages, encoded/decompressed bytes, time, and retries. Exhaustion preserves the receipts and partial root as `partial`/`unavailable`; no silent truncated complete snapshot. Measure caps against selected deployment during acceptance.


### Миграция и восстановление

Reuse legacy roots only after reopening and verifying exact bytes, request/profile/Vary identity, completeness, source relation, and current rights. Legacy 304-without-body or unfenced cursor state is unavailable until recaptured. Suspend the affected route and retain or quarantine bytes under the owner's retention rights; do not roll back a newer correction or revoke.


### Композиция и owners

- The CAP receipt is the supplier input to LIF-03; LIF-03 alone commits the selected cursor/frontier and rejects stale attempts, reset/ABA, or missing prior head.
- A complete snapshot means source-defined cut plus all required continuation pages and exact child bodies. A page count, ETag, hash, or high offset by itself is not completeness evidence.
- Transport safety and source-use/materialization permission both precede capture side effects. LIF-05 fences each actual write/disclosure; LIF-01/03 admission and later CAP-03 reuse consume the lawful representation. An HTTP-valid response is not permission to store it.
- LIF-05/native source-use producer supplies a current, qualified source/profile/purpose/audience/actual-sink decision before the selected CAP-02 body/temp/log/cache placement. CAP-01 outbound-query permission and CAP-03 later reuse admission do not authorize capture storage. If authorized query egress returns a body whose placement is unknown/denied, do not stage/store/log/cache or expose its digest/ref. Discard at the authorized ephemeral processing boundary and emit only a permitted opaque non-admission receipt; if ephemeral response processing itself lacks permission, refuse the fetch. Do not label this a complete admitted capture. See the task conditional supplier: this is a selected-effect join, not a whole-task start dependency.
- HTTP ETag/304 rules apply only to that representation protocol. Existing qualified file, database-query or bounded stream producers retain their native receipt/cut semantics; they are not wrapped in a fictitious HTTP response. WDI first-route evidence neither closes nor blocks a disjoint selected protocol extension.
- For a selected controlled-proxy route, verify an authenticated request-bound enforcement result binding the exact request/attempt, resolved final target, proxy/policy identity and actual egress decision, including redirected hops and credential audience. A client socket peer that is merely the proxy, a forwarding header or proxy configuration is not target evidence. Use the existing transport/security seam; missing or mismatched required evidence refuses that destination/use. Private targets may pass only under the expressly permitted private-connector profile, never public-discovery privilege.


### Acceptance и различающие проверки

- An allowed bounded fetch writes an immutable root and consumer receipt; a second exact use resolves the same bytes without network access and verifies hash/profile.
- 304 without a readable matching root, Vary mismatch, partial transfer, malformed range, validator change, missing required coverage or conflicting duplicate page, oversize body, or stale cursor writer remains partial/unavailable.
- Redirect-to-private-IP, DNS rebinding between check and connect, parser-confused URL, credential-forwarding hop, and disallowed proxy path are blocked at the actual socket/egress boundary.
- Removal of body binding or LIF-03 expected-head fencing while status markers remain makes the matched negative fail.
- Query-only canaries remain absent from managed staging/temp/CAS/log/cache sinks at capture time, not merely after cleanup; permitted receipt/result remains usable. Removing pre-materialization permission while leaving later reuse checks must fail.
- With WDI still honestly single-response, a separately qualified source protocol completes its own capture→receipt→fresh consumer without HTTP-specific assumptions. An unsupported continuation cannot borrow the WDI receipt; removing that protocol’s actual completeness/fence changes its result.
- Controlled-proxy positive: an authorized target with a verified request-bound enforcement result reaches the selected receipt/reader. Through the same proxy, a forbidden metadata/private target, a receipt for another attempt or a forwarding-header substitute must fail; explicitly permitted private-source traffic retains its separate positive. Remove target-result verification while retaining proxy labels: the forbidden-target probe fails. Direct/nonproxy routes use their own actual-boundary proof.


### Входы и ответственность за их получение

- Accepted E02-selected source and producer, endpoint host/path contract, permitted proxy/network egress, credential audience, and DNS/socket enforcement point.
- For pagination/range, the provider's exact snapshot/cut token, continuation, validator, reset, and completeness semantics with documented limits.
- Selected persistence backend and recovery/retention rights; no remote S3/GCS parity is inferred from filesystem support.


### Когда обоснованно отклониться

- If the provider offers no stable cut for pagination, bound the result to the observed window and leave snapshot completeness not established; do not enable resumable cursor progress.
- If a backend cannot enforce LIF-03's conditional head or LIF-05's rights checks, keep the affected profile unsupported rather than adding a parallel cursor or permission owner.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) — ETag identifies and validates a selected representation; If-None-Match can produce 304; 304 carries no representation body; Range/206 is optional and If-Range must use a strong matching validator; HTTP idempotence concerns intended server effect, and clients should not automatically retry a non-idempotent request without a means to know it is safe or detect non-application. **Граница:** HTTP validators are origin assertions about a representation, not cryptographic content hashes, snapshot completeness proofs, rights decisions, or current legal status.
- [RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html) — Cache reuse depends on target, method, freshness or successful revalidation, and Vary-selected request fields; a 304 updates an appropriate stored response, and partial responses require matching representation validators before combination. **Граница:** The HTTP cache model does not admit a PolicyOS use, prove source authority, or ensure that a source's paged records form a stable semantic snapshot.
- [RFC 8288: Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html) — The Link header models typed relations between a current context and target resources and defines parsing and relative-target resolution semantics. **Граница:** A next-like relation is a navigation hint/protocol value, not proof that all pages share a consistent source cut or permission. Every dereference still needs the selected transport and egress policy.
- [OWASP Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) — For known destinations, accept a host from an allowlist and construct the request locally; validate resolved IPv4 and IPv6 targets and bind the connection to an approved address because a separate DNS check does not prevent rebinding; redirects and parser disagreement must not bypass destination checks. **Граница:** This is defensive guidance, not a proof of the repository's proxy, DNS, socket, or firewall behavior; those enforcement points must be verified for the selected deployment.
- [Use delta query to track changes in Microsoft Graph data](https://learn.microsoft.com/graph/delta-query-overview) — Graph's opaque nextLink and deltaLink tokens represent state for a change-tracking round; clients continue until deltaLink, preserve query state, and must handle duplicate/replayed items, processing delay, and expired tokens requiring resynchronization. **Граница:** This is one provider's API contract. It documents that some resource properties outside the main store are not tracked, so a delta feed cannot be generalized into a complete change denominator for other sources.
- [How to prevent object overwrites with conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html) — S3 supports conditional object writes using If-Match/If-None-Match, rejecting mismatched versions with precondition/conflict responses; this is a concrete compare-and-swap pattern for a selected object head. **Граница:** Provider behavior and multipart/delete races are S3-specific; this is a mechanism comparison, not a recommendation to add S3 or evidence of filesystem/CAS parity.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CAP-03"></a>

## CAP-03 — Purpose-aware owner admission and immutable library reuse

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CAP-03]`. Review: [root-review](root-review.md#CAP-03).

### Предпочтительное решение

Wire the selected acquisition route to native passport admission and the governed library resolver. For retention-permitted profiles, keep exact bytes immutable in CAS with a manifest binding content, source receipt, producer/profile/schema and relevant tenant context. For query-only profiles, retain only the permitted result/receipt with verifier provenance and the actual custodian-side binding; do not copy restricted source bytes; store admission and later reuse as append-only owner decisions. LIF-01 owns the specific relation/use admission, and LIF-05 owns rights-sensitive materialization and shared disclosure composition. Each reuse reopens the current purpose, audience, source-right generation, and content binding, while preserving the same exact root. A hash, HTTP 304, source contract, or ODRL permission statement is not by itself an admission decision. Existing filesystem-scoped support does not establish S3/GCS tenant parity.


### Что переиспользовать

- `policy-engine/src/polisyos/runtime/quality/acquisition_executor.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `build_admission_passport/admit_acquisition_with_semantic_epoch/revalidate_admission_passport`. R9's pinned C inventory reports passport construction, semantic-epoch admission, and revalidation; the live producer's terminal result is still pending passport.
- `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CanonicalAcquisitionAuthority.resolve_live_source_execution`. Pinned C inventory reports fresh source/license/catalog resolution; local provision/hash evidence does not establish external institutional grant or signer competence.
- `policy-engine/src/polisyos/core/artifacts/manifest.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ArtifactManifest/ArtifactRef`. Pinned C inventory reports content, schema, producer, lineage, governance, tenant, authority, and integrity fields.
- `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/types.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CatalogFetchBinding/CatalogFetchResolution`. Pinned C inventory reports a typed exact fetch binding/resolution with bound/not-admitted/ambiguous states; consumer use of the bound root remains to be proved.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Connect the CAP-02 persisted root receipt to the existing passport/admission functions; add only owner-approved binding fields absent after E02 rebind.
2. Persist an immutable admission receipt/event bound to exact root, content, profile/schema, purpose, audience, verifier provenance, rule version, and effective/recorded time; make the library resolver return ArtifactRef plus current admission trace.
3. Place cache, reader, resume, export, and materialization paths behind the same source-use and LIF-05 rights-generation decision; recheck on resume and effect/commit, not just first fetch.
4. Consume LIF-05's shared disclosure reserve/commit and indeterminate outcome for AP07 profiles; do not add a per-request counter or duplicate entitlement ledger.


### Рассмотренные альтернативы

- **Mutable latest-file directory, URL-keyed cache, or content hash treated as permission** — It loses exact source/profile/use identity and cannot represent rights or schema changes; a digest proves byte identity only.
- **Create a CAP permission service or disclosure budget** — LIF-01 owns use admission and LIF-05 owns copy/disclosure transitions; another owner would make revocation and shared-release accounting disagree.
- **Use an HTTP cache as the governed library** — HTTP caching solves representation reuse; it does not re-evaluate purpose, audience, tenant, or source rights.


### Free-grow и ресурсы

- **data or config growth:** Supported use purposes and source profiles can grow as versioned owner evidence/config under existing grammar; each new use still requires a fresh owner decision.
- **extension boundary:** A new storage backend or semantic copy-control class requires an explicit backend adapter and LIF-05 conformance/parity evidence; a config flag or local authz label cannot claim remote deletion or custody.
- **resource behavior:** Content-addressing amortizes identical body storage, while manifest/admission traces grow by source generation and use. Bound cache entries and retained bytes using the selected retention contract; evicting a cache entry cannot erase a rights history or turn missing bytes into empty evidence.


### Миграция и восстановление

Do not infer rights from historical artifacts or preseed receipts. Reopen exact roots with current owner evidence and completeness; unavailable roots remain unavailable. On revoke or failed revalidation, disable new reads, cache hits, resume and export under LIF-05, preserve permitted audit history, and separately account for actual copies; already disclosed bytes cannot be recalled by a status change. Append-only is a history-order rule, not permission to retain forbidden bodies, identifiers or digests. Apply LIF-05’s actual retention decision and retain only permitted historical facts, exposing lost replay/verification capability.


### Композиция и owners

- CAP-02 supplies immutable roots; LIF-01 supplies current claim/use-specific relation admission; LIF-05 supplies rights generations, managed-copy boundaries, restore handling, and any shared disclosure accounting.
- A second purpose gets a fresh admission trace even when it resolves the same bytes. Rights to read, process, derive, and publish remain separately scoped where source terms distinguish them.
- For query-only profiles, allowed derived outputs can remain consumable only if the selected rights/sink policy proves raw bytes did not persist in each inventoried CAS, log/trace, browser, backup, or provider temporary sink.
- Selected cost-dependent route consumes the actual acquisition_planner native cost artifact, also supplying DEB-13 net-value composition. DEB-07 records the source-row disposition without a second writer. For the source-selected free WDI route, the canonical runtime/quality/acquisition_planner.py cost-schedule owner may admit dated expert_hours/calendar_days/collection_mode effort under the principal’s 2026-09-17 option A: first inspect actual connector/comparable-ingest evidence, prefer measured comparable effort, otherwise explicitly label and justify the owner estimate. Neither fixture hours/days nor a cap is the basis. A paid/licensed selected source invalidates that premise and needs its real quote/rights evidence; no default institutional price request for free-data engineering.
- Fresh-use qualification is a current predicate, not compulsory repetition of every expensive verifier or full payload scan. Reuse an immutable content-bound assessment only for its exact semantic input/rule/verifier/profile closure and allowed lifetime; resolve current purpose/audience, rights, claim/source generations and publication fence on every affected use. Cache keys include relevant negative/membership dependencies; TTL or equal bytes alone is insufficient. Unknown dependency coverage or an unavailable required freshness fence triggers scoped requalification, limitation or refusal. Preserve per-use binding/decision through the native owner, without duplicating assessment payloads.


### Acceptance и различающие проверки

- An admitted root promotes once and is resolved by exact content for a fresh allowed use with a new purpose decision.
- Revoke/expiry/purpose, audience, tenant, profile, schema, source generation, or verifier change between admission and resume/cache/export blocks the fresh effect even while an old passport/marker remains.
- Remove content resolution/verifier provenance but preserve `admitted` and hash labels; promotion and the actual consumer read must fail.
- For query-only mode, controlled raw-byte canaries are absent from all selected sinks while the permitted derived result and receipt remain usable.
- Same-root repeated authorized reuse need not rerun the immutable assessment, but a rights/purpose/generation change still changes fresh admission. Deletion restrictions apply to identifying lineage and receipts as well as payloads; restore cannot resurrect their prior access.


### Входы и ответственность за их получение

- Accountable source/custodian grant or other competent owner evidence for each purpose, audience, jurisdiction, duration, and recipient.
- Selected backend's actual tenant isolation, read, restore, backup, deletion, and cache behavior, plus the complete sink inventory for the claimed profile.
- For AP07, the source/custodian's protected unit, alias/overlap and lineage rules, recipient scope, replay-versus-fresh-draw rule, and composition law.


### Когда обоснованно отклониться

- If external grant or backend copy control cannot be verified, retain capture only in the permitted quarantine scope and mark reuse unadmitted; do not claim filesystem behavior transfers to remote storage.
- If source composition law is unavailable, refuse the affected aggregate/query output rather than inventing a universal privacy budget.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html) — Cache reuse depends on target, method, freshness or successful revalidation, and Vary-selected request fields; a 304 updates an appropriate stored response, and partial responses require matching representation validators before combination. **Граница:** The HTTP cache model does not admit a PolicyOS use, prove source authority, or ensure that a source's paged records form a stable semantic snapshot.
- [ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/) — ODRL supplies an interoperable model for asset-linked permissions, prohibitions, duties, parties, and constraints, useful as an input vocabulary for purpose/use evidence. **Граница:** An ODRL expression can state a policy but does not authenticate its issuer, establish signer competence, decide legal force, or prove that a custodian granted the asserted permission.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O separates entities, activities, and agents and connects used/generated entities with responsible agents and times, a useful reference for capture and transformation provenance. **Граница:** A provenance graph records asserted relationships; it does not make an agent's assertion true or supply authority, permission, or verification.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CAP-04"></a>

## CAP-04 — Source-specific change event producer and acquisition consumer

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CAP-04]`. Review: [root-review](root-review.md#CAP-04).

### Предпочтительное решение

Add only source-specific change/retraction/rights event producers next to their accountable source owner, then hand the exact event into LIF-02's existing enrollment, replay, generation, and publication-currentness fence. Bind event identity, exact old/new source root or relation, source generation, verifier/issuer evidence, source journal, recorded time, effective time, and affected audience. CAP emits events; it does not create another universal cascade or scheduler. Until a source has a complete event/change contract, its currentness remains limited to an explicit as-of cut or unclaimed. The academic work-ID retraction parser remains a narrow adapter, not proof of general update coverage. Support both a source-native feed and an explicitly observed snapshot-comparison route. For the latter, CAP-02 supplies comparable permitted observations; CAP-04 persists the exact observed old/new representations, selector/profile/coverage and acquisition times, without inventing source-effective time or completeness between polls. Local journal positions order our observations only. A detected disappearance, access failure or changed representation is not by itself repeal/retraction or a whole-source deletion. Qualified observations can invalidate dependent use through LIF-02; unchanged reads justify only the measured scope/cut and cannot erase missed transients.


### Что переиспользовать

- `policy-engine/src/polisyos/scientist/evidence/claims/head_index.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ClaimDependencyFieldRegistry/ClaimDependencyDenominatorReceipt/ClaimLedgerOwnerPort`. Pinned C inventory reports a dependency denominator and owner-port seam; source-root event wiring is not established there.
- `policy-engine/src/polisyos/runtime/quality/epoch_validity_cascade.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `epoch_validity_cascade`. Existing generation/event cascade is the shared lifecycle path; CAP must supply source-qualified events rather than duplicate invalidation.
- `policy-engine/src/polisyos/scientist/validation/decision_validity.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DecisionValidityService`. Pinned C inventory reports current-projection and event seams; full source enrollment/replay/publication-fence path remains unproven.
- `policy-engine/src/polisyos/data_forge/domains/academic/batch/claim_adjudicator.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `_parse_retracted_ids`. R9 inventory reports source-specific academic retraction by work ID only.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.


### Последовательность реализации

1. Choose a selected source and bind either its supported change journal or its bounded observation/reconciliation route; state coverage, replay/reset behavior, stable identities and what changes the route cannot observe.
2. Implement a typed source adapter that persists event receipts and binds them to CAP-02 roots/relation versions; treat provider events as supplied evidence and verify their source/issuer through the accountable owner.
3. Enroll the dependency denominator and replay the source interval through LIF-02; make publication/currentness participate in its source/right cut fence or expose the accepted bounded cutoff.
4. Make a fresh claim/decision consumer show historical publication separately from current validity; no scheduler may be required for an authority read to refuse a stale green projection.
5. For a source without a feed, compare complete selected observations through its existing capture/decoder owner. Emit an observed-change/coverage-loss fact with the exact local observation basis; preserve source-effective semantics as unknown until their owner verifies them. Failed/partial polls cannot certify unchanged state or manufacture removals.


### Рассмотренные альтернативы

- **Generic polling or ETag change as universal legal/source event** — An ETag change identifies a changed representation, not the affected semantic claim or legal consequence; polling without a source cut cannot prove no missed event.
- **Build a CAP-owned invalidation cascade and scheduler** — LIF-02 owns dependency enrollment, replay, source generations, and currentness fencing; duplication creates divergent green states.
- **Treat a webhook's arrival as a complete denominator** — Delivery may be delayed, replayed, omitted, or expire; provider-specific source contracts and reconciliation cut are still required.


### Free-grow и ресурсы

- **data or config growth:** New sources instantiate a supported feed or observation/reconciliation profile in the existing source registry; a new event/observation semantic class needs its own adapter, without central routing edits.
- **extension boundary:** New event kinds or source-specific semantics require a typed producer and conformance contract; no hand-maintained capability list in central routing and no event-type string promoted by presence.
- **resource behavior:** Replay/fanout work is bounded by enrolled dependencies and retained source cursor; lag, replay-floor expiry, event storm, or missing interval yields pending/limited status and durable work receipts, not a currentness claim.


### Миграция и восстановление

Do not infer enrollment from positive references or verified events from URL movement. Reconcile legacy dependencies against source owner and replayable journal; irrecoverable gaps remain limited. If event verification or replay is withdrawn, mark affected claims pending/limited and preserve append-only history without deleting earlier publication records.


### Композиция и owners

- LIF-02 exclusively owns C/W enrollment, replay floor, duplicate/effect ordering, generation, affected-claim reaction, and public currentness fence; CAP only supplies a verified source-specific event or bounded source read.
- A provider delta token may be an opaque cursor and snapshot witness only under that provider's contract; replays are idempotently reconciled, expired tokens trigger bounded resync, and a feed with undocumented omissions cannot support completeness.
- Recorded, effective, retrieved, and publication times remain distinct; source change does not itself establish correction, repeal, or legal applicability.
- LIF-02 consumes local observation-cut identity/coverage through its explicit bounded-observation branch; our journal closes local enrollment races but cannot supply source continuity or effective time. Selected fresh projections retain observation/as-of limitations.


### Acceptance и различающие проверки

- A material change on an enrolled source produces persisted event → scoped invalidation → fresh consumer currentness status; an unrelated source remains current.
- Event-before-enrollment, backdated event, replay/duplicate, missing journal segment, stale index, replay-floor expiration, rights race, and scheduler-off read cannot leave an unjustified green current projection.
- Remove source generation/dependency binding while leaving an event and current marker; the fresh consumer must refuse green.
- Surface shows event source, verifier/cut basis, source/effective time, limitations, and historic publication separately.
- A no-webhook source changes its observed representation: the authorized poll persists an observed delta and a fresh affected claim changes without invented source-effective time. A→B→A between polls remains unobserved; partial/failed polls and selector drift cannot certify no change or semantic repeal. Removing actual comparison while retaining poll heartbeat fails the observed-change positive.


### Входы и ответственность за их получение

- Existing source feed/correction protocol where available, or actual selected observations and a permitted polling/reconciliation recipe. A missing feed is external only for claims requiring that feed’s continuity, not for implementing observed-change detection.
- Claim-type-specific owner rule mapping a changed source relation to affected dependencies; no generic equivalence from bytes to legal effect.
- LIF-02's accepted source generation, replay, and publication-fence interface.


### Когда обоснованно отклониться

- Without a complete source journal or supported cut, do not claim complete intervening event history/currentness. Continue bounded authorized observation, explicit as-of/coverage limits and affected-use reaction; never relabel scraped observations as a source-authoritative feed.
- If an event cannot be tied to a verifier-qualified source/relation, retain it as a candidate and do not advance authority-grade current status.

Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.


### Исследование и предел переноса

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) — ETag identifies and validates a selected representation; If-None-Match can produce 304; 304 carries no representation body; Range/206 is optional and If-Range must use a strong matching validator; HTTP idempotence concerns intended server effect, and clients should not automatically retry a non-idempotent request without a means to know it is safe or detect non-application. **Граница:** HTTP validators are origin assertions about a representation, not cryptographic content hashes, snapshot completeness proofs, rights decisions, or current legal status.
- [Use delta query to track changes in Microsoft Graph data](https://learn.microsoft.com/graph/delta-query-overview) — Graph's opaque nextLink and deltaLink tokens represent state for a change-tracking round; clients continue until deltaLink, preserve query state, and must handle duplicate/replayed items, processing delay, and expired tokens requiring resynchronization. **Граница:** This is one provider's API contract. It documents that some resource properties outside the main store are not tracked, so a delta feed cannot be generalized into a complete change denominator for other sources.
- [What is ELI?](https://eur-lex.europa.eu/eli-register/what_is_eli.html) — ELI offers persistent identifiers and a common metadata model for legislation, including identifiers and descriptive/version information that support machine-readable legal-source discovery and citation. **Граница:** An identifier or metadata record does not prove the authenticity of the fetched bytes, current legal effect, jurisdictional applicability, or an institution's interpretation.
- [Verify the authenticity of an electronic edition of the Official Journal](https://eur-lex.europa.eu/content/help/oj/authenticity-eOJ.html?locale=en) — For the EU Official Journal, the electronic edition is the authentic legally effective edition from 1 July 2013, and its signature-verification procedure checks that the signed edition is authentic and unchanged since signature. **Граница:** This route is specific to the Official Journal and the applicable EU legal rule. It does not make every EUR-Lex page, consolidation, translation, or linked record independently authoritative.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CAP-05"></a>

## CAP-05 — Official/legal source relation and temporal applicability

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CAP-05]`. Review: [root-review](root-review.md#CAP-05).

### Предпочтительное решение

Build a jurisdiction/source-specific capture-to-relation adapter over the shared CAP-02 root and CAP-03/LIF-01 use admission. A verifier must bind exact official artifact bytes/version to a source relation and the appropriate claim-type grounds, with authority/issuer evidence, scope/jurisdiction, citation, original language, translation relation/challenge, rule version, and distinct publication, effective, retrieved, and assessment times. Reuse the existing Lex applicability and citation/document owners after accepted-source rebind. ELI is a useful identifier/metadata route; signed official publications such as the EU e-OJ and GovInfo authenticated documents provide jurisdiction-specific authenticity evidence. Neither a URL, signature bit, hash, nor document identifier proves signer competence or legal applicability by itself. Keep LLM and parser outputs at candidate level and show unresolved legal issues as limited/refused.

### Что переиспользовать

- `policy-engine/src/polisyos/data_forge/domains/legal/source_relation.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `require_legal_source_relation_verification`. Pinned C inventory describes a legal relation refusal path, not an event producer. The file is absent at planning HEAD dc075, so this anchor is historical pending accepted-E02 rebind; do not recreate it by assumption.
- `policy-engine/src/polisyos/lex/normpack/applicability.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `Lex applicability owner`. R9 pinned inventory assigns temporal/legal applicability here; exact accepted owner and current schema require rebind.
- `policy-engine/src/polisyos/ir/loading/citations.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `CitationRef`. R9 pinned inventory reports the typed citation reference seam.
- `policy-engine/src/polisyos/ir/world/doc.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `DocMeta/DocFragment`. R9 pinned inventory reports document metadata/fragments for original text and legal-unit representation.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. For the selected jurisdiction, name the legally recognized publication/official source, authentic representation and competent verifier; pin the exact artifact/version to the CAP-02 root.
2. Resolve the source relation through LIF-01 with claim-type-specific grounds: legal text/citation can ground text and legal-source facts, but causal or measurement claims need their own B01-prescribed grounds.
3. Pass exact law/version/effect/applicability premises to the selected legal consumer; let the native applicability owner resolve jurisdiction and time, and LIF-02 consume source-change events where currentness is claimed.
4. Carry original-language and translation occurrence separately; route a challenge to the exact translation and reassess only affected uses/claims. Surface all unresolved premises and avoid claiming a notice or institutional action without recipient evidence.

### Рассмотренные альтернативы

- **Treat an ELI/URL/hash/signature as the legal authority decision** — Identifiers and integrity evidence locate or protect bytes; they do not establish source competence, legal force, scope, effect time, or application to the target.
- **Scrape a convenient aggregator or promote LLM summaries** — It obscures authentic version/citation and turns candidate text into authority without the source relation and competent legal owner.
- **Build one universal legal authority engine** — Jurisdictions differ in authentic publication, consolidations, time rules, translations, and verifier competence; the existing Lex owner and typed source adapters should compose claim-specific grounds.

### Free-grow и ресурсы

- **data or config growth:** Add jurisdiction/source profiles with source identifiers, version conventions, authentic format, and owner verifier configuration under the existing legal-source and applicability grammar.
- **extension boundary:** A new jurisdictional signing format, legal event semantic, or relation type requires a reviewed typed verifier/adapter and claim-type conformance. A URL prefix, certificate flag, or parser label never auto-admits it.
- **resource behavior:** Retain exact version/citation and a compact verification proof; bounded parsing/OCR/translation records preserve unsupported fragments, uncertainty and challenges. Unsupported source or version remains unclaimed rather than silently using a nearby edition.


### Миграция и восстановление

Re-resolve legacy legal roots against a source-specific verifier and exact jurisdiction/time basis. Do not backfill official standing, signer competence, custody, force, scope, or recipient from URL, digest, or signature presence. On verifier, source, translation, or rule withdrawal, downgrade the current projection and preserve permitted historical citations/publications and the event trail.


### Композиция и owners

- LIF-01 admits a specific relation and use; legal-source evidence remains distinct from causal, measurement, mandate, value, and assurance grounds under SDD-B01.
- If a consumer uses a joint legal premise/witness, SDD-C01 permits an exact validated joint witness only for the property it proves, with assumptions, consumer, and falsifier; pairwise facts or a signature cannot stand in for it.
- Any inferential method used to resolve uncertainty is named and scoped to the claim under SDD-C02; a Bayesian-only path is not mandated, and method outputs cannot mutate authority without the relation/use verifier.
- When legal source changes affect a published claim, CAP supplies the qualified source event and LIF-02 alone owns enrollment, invalidation, and currentness at publication.


### Acceptance и различающие проверки

- A verified source artifact at a jurisdiction/date resolves to an exact citation, source relation, applicability result, and fresh consumer decision; a changed version emits a distinct source event/currentness reaction.
- Spoof URL, digest/version mismatch, invalid or revoked signer chain, non-competent issuer, wrong jurisdiction/effective time, translation challenge, late correction/repeal, or absent recipient evidence refuses or limits the affected claim.
- Remove verifier provenance/relation binding while retaining citation and `verified` marker; the legal consumer refuses authority.
- Falsify a claimed semantic relation while keeping the text, source signature, and model fit: authority must not survive. Explicit hypothetical assumptions remain candidate analysis and never become a principal's legal or value decision.


### Входы и ответственность за их получение

- Selected jurisdiction and exact official publishing source, authentic-version rule, qualified source/issuer verification evidence, and competent institutional/legal relation owner.
- Law-specific promulgation, effective, amendment/repeal, territorial, transitional, and consolidation semantics plus source correction/change feed.
- Original and translation text, translation provenance, challenge process, and recipient evidence before any notification claim.


### Когда обоснованно отклониться

- If no competent verifier or authentic-version rule is available, preserve source text/citation as candidate evidence and mark legal applicability `not_established`; do not invent a source_relation producer in a refusal seam.
- If a source's legal effect requires a human/jurisdiction-specific determination, integrate that typed determination as evidence and keep the institution's legal act external to PolicyOS.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [Verify the authenticity of an electronic edition of the Official Journal](https://eur-lex.europa.eu/content/help/oj/authenticity-eOJ.html?locale=en) — For the EU Official Journal, the electronic edition is the authentic legally effective edition from 1 July 2013, and its signature-verification procedure checks that the signed edition is authentic and unchanged since signature. **Граница:** This route is specific to the Official Journal and the applicable EU legal rule. It does not make every EUR-Lex page, consolidation, translation, or linked record independently authoritative.
- [What is ELI?](https://eur-lex.europa.eu/eli-register/what_is_eli.html) — ELI offers persistent identifiers and a common metadata model for legislation, including identifiers and descriptive/version information that support machine-readable legal-source discovery and citation. **Граница:** An identifier or metadata record does not prove the authenticity of the fetched bytes, current legal effect, jurisdictional applicability, or an institution's interpretation.
- [Regulation (EU) No 910/2014 (consolidated text)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02014R0910-20240520) — The regulation defines electronic seals as linked to origin/integrity and gives qualified seals specified evidentiary presumptions; it also defines qualified timestamp and trust-service semantics. **Граница:** The specific legal effect depends on the applicable legal regime and trust chain. A verified seal alone does not establish that the signer had authority to issue the legal act or that the act applies to a target policy question.
- [Authentication and the 2026 Code of Federal Regulations](https://www.govinfo.gov/about/authentication) — GovInfo's digitally signed publications support verification of certification, integrity, and signer identity at signing; its CFR documentation directs users to the Federal Register and List of CFR Sections Affected to identify amendments and warns that publication and effective dates differ. **Граница:** This U.S. publication model is jurisdiction-specific; a signed edition still requires its amendment/effective-time context and a source-qualified legal applicability decision.
- [ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/) — ODRL supplies an interoperable model for asset-linked permissions, prohibitions, duties, parties, and constraints, useful as an input vocabulary for purpose/use evidence. **Граница:** An ODRL expression can state a policy but does not authenticate its issuer, establish signer competence, decide legal force, or prove that a custodian granted the asserted permission.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O separates entities, activities, and agents and connects used/generated entities with responsible agents and times, a useful reference for capture and transformation provenance. **Граница:** A provenance graph records asserted relationships; it does not make an agent's assertion true or supply authority, permission, or verification.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.

<a id="CAP-06"></a>

## CAP-06 — Restricted/private source and remote-compute outcome binding

Исходная запись: [tasks.json](../tasks.json), `tasks[id=CAP-06]`. Review: [root-review](root-review.md#CAP-06).

### Предпочтительное решение

Reuse local AccessScope/classification checks as one input to a pre-effect decision, while requiring external source/custodian grants and disclosure policy through LIF-01/LIF-05. Use the existing ControlPlaneStore/ControlWorker and LIF-04 to persist intent, attempt, provider effect, receipt, and local completion as distinct states. Bind each dispatch to exact input roots, query digest, executable/container digest, purpose, tenant, recipient, schema, and idempotency key. Ask the selected provider for request-key replay plus authoritative lookup/cancel semantics; persist the intent before sending. A lost reply or expired idempotency window remains `pending`/`indeterminate` until reconciled, never success and never permission for a blind repeat. LIF-05 alone owns copy/sink and AP07 disclosure composition; if no verifiable custody/no-retention contract exists for the selected profile, refuse it or leave it unclaimed.

### Что переиспользовать

- `policy-engine/src/polisyos/core/security/access_scope.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `AccessScope`. Pinned C inventory reports tenant/cell/identity/role/PII context; it is not an external grant or provider receipt.
- `policy-engine/src/polisyos/fabric/security/access_control.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `classification_allowed`. Pinned C inventory reports local classification and purpose checks; they do not establish source-specific legal permission or provider custody.
- `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `runtime-operation intent/recovery store`. LIF-04's pinned owner map reports a durable local intent/transaction seam; remote outcome/reconciliation semantics remain provider-specific.
- `policy-engine/src/polisyos/runtime/http/services/control_worker.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `ControlWorker.dispatch_once`. Pinned owner map reports an existing worker loop/lease; it is the worker extension point, not proof of external exactly-once completion.
- `policy-engine/src/polisyos/fabric/data_plane/orchestrator.py@dccea950845cda5b38f026e7770c07819d31f4d9` — `PartitionedIngestionPlan/run_partitioned_ingestion`. R9 owner map reports local partition/fetch orchestration; provider-specific remote receipt remains a separate typed input.

Наблюдение на историческом pin не устанавливает текущую реализацию или принятую базу.

### Последовательность реализации

1. Select one real source/provider/profile and resolve source-use permission, purpose, tenant, recipient, retention/logging, and output policy before dispatch; do not treat local PII/classification labels as the external grant.
2. Persist an LIF-04 intent and attempt with stable idempotency identity and request digest before sending the exact bound query/input and executable version; store provider job ID, signed/otherwise verifiable receipt, provider idempotency horizon, and response identity.
3. On response or recovery, perform provider lookup/reconciliation against the same request digest, source roots, executable, recipient, and output hash; publish only after owner validation and a fresh rights/currentness check.
4. Use LIF-05's shared rights/disclosure transition at query, resume, cache, export, restore, and output-admission boundaries. Inventory selected raw-byte sinks, including CAS, logs/traces, browser state, backups, and provider temp outputs; test with controlled canaries.

### Рассмотренные альтернативы

- **Blindly retry POST after timeout or assert exactly-once from a local idempotency key** — RFC 9110 says non-idempotent requests cannot safely be retried absent a detection/idempotency mechanism. Provider keys may expire; Stripe documents a finite key horizon and cached response behavior, so its behavior cannot be assumed elsewhere.
- **Treat a locally permitted tenant/role as a custodian grant** — Identity and classification describe local access context, not external rights, recipient cooperation, data processing terms, or provider retention.
- **Adopt a TEE as a universal no-retention/legal-compliance proof** — Attestation can bind measured code and isolate memory under a provider model; it does not prove legal permission, correct output, every side channel/log/backup, or deletion.

### Free-grow и ресурсы

- **data or config growth:** Add a new provider profile through the typed remote-effect registry only after it declares request identity, idempotency/lookup/cancel, receipt, retention, output, and copy semantics.
- **extension boundary:** A genuinely new remote protocol needs a reviewed typed adapter and selected-backend conformance; no arbitrary endpoint, self-asserted job completion, or central hardcoded provider fallback becomes executable.
- **resource behavior:** Bound queue attempts, provider concurrency, bytes, execution time, polling/cooldown, and output size by the selected deployment/provider contract. Unknown outcome retains the shared LIF-05 reservation and LIF-04 duty until reconciliation or an explicit refusal/timeout disposition; no numeric budget is claimed before measurement.


### Миграция и восстановление

Legacy remote jobs without exact provider receipt/request digest remain indeterminate; local authz does not backfill grants. Block new dispatch on provider/profile compromise or revoke; reconcile in-flight unknown effects before status changes, preserve receipts, and quarantine/restored copies under LIF-05. Never return an uncertain disclosure reservation or old authority after revoke.


### Композиция и owners

- LIF-04 owns durable intent, attempt, effect, idempotent retry, cancel race, recovery and local completion. CAP supplies provider-specific receipt/query semantics; it does not add a second queue or status plane.
- LIF-05 owns current rights, managed-copy enrollment/restore, AP07 protected-unit overlap, atomic reserve/commit, replay-versus-fresh-draw rules, and uncertain-output holds. CAP-03/06 consume the same decision.
- LIF-01/05 permission checks bind exact roots, executable, purpose and recipient; returned output is a new candidate artifact until its exact content and provider receipt are validated.
- Attestation is one optional evidence input about a measured compute image, not proof that an institution granted use or that every external sink is controlled.


### Acceptance и различающие проверки

- A permitted synthetic job resolves a provider receipt bound to input root, executable digest and recipient, and only an owner-validated output becomes a usable artifact.
- Provider accepts then response is lost; retries use same digest/key while the provider horizon holds, then lookup or indeterminate recovery is required. Expired key, lost lease, cancel race, swapped output, wrong tenant/recipient, revoked grant, or unavailable control store never produce green or blind duplicate work.
- Fresh resume/cache/export after a revoke is blocked even when an old receipt exists; a new recipient/fresh draw or aliased overlapping release follows the same LIF-05 composition owner.
- For query-only, raw-content canaries are absent from every inventoried local and provider-controlled sink while an allowed derived result remains consumable; removal of the sink guard or fresh rights check fails that property.


### Входы и ответственность за их получение

- Accountable source/custodian permission, purpose-specific allowed query/output, recipient and cooperation scope, and current source-right generation.
- Chosen provider's documented and contractually applicable idempotency retention, request-digest comparison, lookup, cancel, receipt signature, log/retention/temp-storage, and status semantics.
- Selected remote backend's tenant isolation, restore/revoke protocol, storage/backup topology and any independently verifiable attestation/retention evidence.


### Когда обоснованно отклониться

- If the provider cannot look up an uncertain effect and its idempotency window is expired or unknown, leave the duty indeterminate and do not automatically issue a fresh effect.
- If provider temp/log/backup behavior cannot support the selected no-raw-persistence profile, refuse that profile; a narrower query-only or local/custodian-side computation may be considered under a separately admitted contract.


Classify each input at accepted-source rebind as internal engineering output/allocation, existing source record, or genuine external fact/permission. Missing native producer/bridge is assigned work, not an external blocker. Only the last class can justify an external-input hold after supplier/alternative investigation. See root-review.md for the task-specific distinction.

### Исследование и предел переноса

- [RFC 9110: HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) — ETag identifies and validates a selected representation; If-None-Match can produce 304; 304 carries no representation body; Range/206 is optional and If-Range must use a strong matching validator; HTTP idempotence concerns intended server effect, and clients should not automatically retry a non-idempotent request without a means to know it is safe or detect non-application. **Граница:** HTTP validators are origin assertions about a representation, not cryptographic content hashes, snapshot completeness proofs, rights decisions, or current legal status.
- [Idempotent requests](https://docs.stripe.com/api/idempotent_requests) — Stripe documents request-key replay that returns the stored first result, checks parameter equality, and may prune keys after at least 24 hours; concurrent requests and pre-execution validation failures have separate behavior. **Граница:** This is a vendor-specific bounded idempotency window, not exactly-once execution or a universal provider contract. Once the key expires, a replay may execute again.
- [Cryptographic attestation - AWS Nitro Enclaves](https://docs.aws.amazon.com/enclaves/latest/user/nitro-enclave-concepts.html) — Nitro uses signed attestation documents with enclave measurements that an external service or AWS KMS can check before authorizing selected operations. AWS documents that enclaves have isolated memory/vCPUs, no persistent storage or direct external network connectivity, and communicate through the parent instance's vsock path. **Граница:** This proves a bounded execution identity under the provider's model, not legal permission, correct result semantics, upstream raw-source truth, every external log/temp sink, or post-run deletion. Third-party verifiers need their own policy and validation.
- [ODRL Information Model 2.2](https://www.w3.org/TR/odrl-model/) — ODRL supplies an interoperable model for asset-linked permissions, prohibitions, duties, parties, and constraints, useful as an input vocabulary for purpose/use evidence. **Граница:** An ODRL expression can state a policy but does not authenticate its issuer, establish signer competence, decide legal force, or prove that a custodian granted the asserted permission.
- [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) — PROV-O separates entities, activities, and agents and connects used/generated entities with responsible agents and times, a useful reference for capture and transformation provenance. **Граница:** A provenance graph records asserted relationships; it does not make an agent's assertion true or supply authority, permission, or verification.

Ссылки подтверждают только указанный внешний механизм; выбор для PolicyOS — инженерный вывод, требующий собственного source-bound proof.
