# Scholar (`polisyos.scholar`)

`polisyos.scholar` builds deterministic knowledge bundles from `ResearchIntent` inputs and seed
sources. It orchestrates discover, acquire, docs, claims, reconcile, and bundle persistence while
staying CAS-first and freshness-aware.

## Role in System

- **Depends on:** `core.contracts.scholar`, `core.artifacts`, `fabric.docs`, `fabric.claims`, `fabric.world`, and shared extractor entry points.
- **Used by:** `scientist` nodes, the scholar CLI/component surface, and tests for bundle generation.
- **Boundary function:** keeps knowledge-bundle creation separate from downstream consumers of the bundle.
- **W7.D requirement bridge:** consumes `polisyos.scholar_requirement.ScholarSupportRequirementSpec`
  when binding literature to Policy Design Case claims; publication evidence may
  support or contest academic claims, but it cannot imply affected-person
  representativeness.

## Key Concepts

- **Deterministic pipeline** - the bundle id is derived from intent, document versions, claims, and policy ids.
- **Freshness** - freshness metadata and sidecar state keep bundles refresh-aware.
- **Discovery/acquire** - seed sources are normalized, canonicalized, and fetched from local files, URLs, or bytes.
- **HTTP destination binding** - public seed and search fetch facades share `discover.transport.fetch_raw`; by default, every URL and redirect hop must resolve only to globally routable addresses, is resolved once, dialed through its selected numeric address, and checked against the connected socket peer while retaining hostname-based Host/SNI identity. The existing `allow_private_networks=True` opt-in preserves private-network use; multicast, reserved, and unspecified checks remain explicit. Controlled redirect cycles are refused by urllib's bounded redirect lifecycle through the shared transport and both adapters. Proxy routes with no destination-binding proof fail closed. A recognized `NO_PROXY` environment bypass is supported; on Python 3.14/macOS, SystemConfiguration wildcard exceptions may fail closed because urllib receives `hostname:port`. No broader proxy-bypass behavior is claimed.
- **Search citation spans** - snippet text may trim boundary whitespace; its start/end character offsets select exactly the returned text from the input page string.
- **Search source binding** - bundle consumers re-resolve the selected raw-page CAS view, check its manifest and content digest, re-run Scholar's extractor/sanitizer, and require each citation span to equal its exact source substring. Legacy artifact-ID-only bundles use the default manifest view with a profileless warning; unavailable or mismatched raw snapshots cannot verify snippets.
- **Docs/claims/reconcile** - document ingestion and claim extraction feed into conflict resolution and filtering.
- **CAS and world events** - bundles and reports are persisted into CAS and accompanied by world events.
- **Claim-bound Scholar requirements** - search, support links, dependence
  records, and spine bindings can carry per-claim publication tier, recency,
  replication, independence, and participation-boundary requirements.

## Public API

- `ScholarService`
- `enrich_topic`
- `ScholarPolicy`
- `EnrichResultV1`
- `EnrichmentReportV1`
- `KnowledgeBundlePayloadV1`
- `persist_knowledge_bundle_payload` for persisting that typed payload through the canonical Scholar CAS writer.
- error types: `ScholarError`, `ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`, `ScholarDocsError`, `ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`

The canonical bundle writer preserves the existing `scholar.knowledge_bundle` kind, JSON media type, schema, and declared input references. It admits finite floating-point fields in `KnowledgeBundlePayloadV1`; non-finite values remain refused. Persisting a bundle does not establish source licensing, currentness, or evidentiary quality. Scholar bundle and report persistence uses the versioned JSON artifact contract; Python object pickling is outside the documented persistence boundary.

## Deep-Research Artifact Compatibility

The canonical Scholar `WebEvidenceBundle` has a proposed additive 1.1
provider-attempt trace, pending G selection. Version 1.0 remains readable with
attempt detail absent; old CAS objects are not rewritten. If a legacy bundle is
resumed into a new 1.1 candidate, old free-text errors become
`legacy_error_not_established`, with attempt history still unknown. Every 1.1 query
and frontier error is fixed-category data even when attempt detail is absent. The
candidate producer would write 1.1, but that behavior is not accepted for
publication until G selects it. The trace records
observed calls, causes, and value-free error categories only; exception messages,
request URLs, credentials, search terms copied from exceptions, and response
payloads are not persisted. Legacy public search calls retain their error text.
This does not add a supported Python facade symbol or HTTP endpoint. It is not evidence of a complete provider roster,
global search exhaustion, or absence of relevant knowledge.

## Shared HTTP Fetch Route

Candidate behavior: `polisyos.scholar.discover.fetch_url` and `polisyos.scholar.search.fetch_open_page` retain their
existing inputs and result types. Both converge on the same redirect-aware transport. With the
default constraints, every hop must resolve to globally routable addresses; explicit private,
loopback, link-local, multicast, reserved, and unspecified guards remain at the shared address
intake. The existing `allow_private_networks=True` option continues to opt into private-network
addresses. Direct routes bind each validated hop to its selected numeric address and verify
`getpeername()`; HTTP Host and TLS SNI continue to use the requested hostname. The shared route
refuses a controlled A/B/A redirect cycle at urllib's bounded loop guard; the v4 RAW tests exercise
the shared primitive and both public adapters. Ambient proxy routes cannot prove the proxy's
resolution of the target, so configured non-bypassed proxy routes fail closed. A `NO_PROXY`
environment bypass is supported when urllib recognizes the supplied `hostname:port`. On Python
3.14/macOS, some SystemConfiguration wildcard exceptions match a hostname but not the
`hostname:port` value passed to urllib, so those legitimate bypasses fail closed. This compatibility
limitation requires owner/G rollout review; the runtime does not infer a trusted proxy contract.

## Saved Fetch Policy and Snapshot Handoff

Cache reuse is a saved-content admission, not a new connection. Before returning a
page, `fetch_open_page` checks the current offline URL/domain/literal-IP policy for
the initial URL, every redirect and final URL, MIME, actual raw byte size and known
acquisition profile. An eligible saved page requires no DNS or socket access. A
missing historical fact or newly denied policy returns a cache-ineligible result;
refresh is explicit, never a hidden fallback. Live misses retain numeric destination,
peer, redirect, proxy and hostname SNI checks at the shared transport owner.

Actual successful acquisition records versioned `fetch_profile`1.0: normalized
constraints, applied raw maximum, timeout, user agent and transport interpretation.
These are acquisition facts, not licensing or institutional permission. The selected
raw `ArtifactRef` survives bytes normalization into the actual acquisition recheck.
A current cache entry cannot supply missing provenance for another selected snapshot
or acquisition, even when the URL or document bytes match.

| Contract | Producer and consumer compatibility | Decision |
| --- | --- | --- |
| WebEvidenceBundle1.0 | Historical reader; absent attempt detail remains unknown | Preserve historical bytes and reads |
| WebEvidenceBundle1.1 | Current candidate attempt-trace producer and reader | Keep candidate; G ratification remains separate |
| Saved fetch_profile1.0 | Actual fetch producer, cache reload, SourceMetadata and API seed | Forward facts only; historical empty profile stays unknown |
| Direct HTTP/TLS on Python3.14 | Both seed and search adapters use numeric peer/hostname SNI guards | Supported controlled local qualification; no live retrieval-quality claim |
| Ambient non-bypassed proxy | Cannot establish target destination binding | Refuse; retain the documented macOS NO_PROXY limitation |

Search failover receives one absolute monotonic deadline. Each physical attempt is
bounded by the remaining wall budget; an unstarted provider is not recorded as an
empty search. A final-batch cutoff remains partial and does not mean global knowledge
exhaustion. Provider exceptions and caller cancellation keep their distinct semantics.

## Current State

- Last updated: 2026-10-19
- Discovery remains under `discover/`; enrichment policies, freshness evaluation/state, staged errors, and pipeline support DTOs are owned by `orchestrator/`.
- Persisted Scholar bundle/report contracts are defined in `core.contracts.scholar` and re-exported from this facade.

## Evidence Validation Facade

The root facade exports `SourceSnippet`, `WebEvidenceBundle`, `validate_source_snippet_spans`, and `validate_web_evidence_source_binding`. The same Scholar validators remain the evidence-admissibility predicates used by Scientist consumers; moving their imports does not replace exact source-byte and span verification with shape checks.

## Python Import Compatibility

The supported Python entrypoint is `polisyos.scholar`; its existing 30 root exports retain
their names and object bindings. The six former private module paths
(`polisyos.scholar.errors`, `.freshness`, `.freshness_store`, `.policies`, `.provenance`, and
`.types`) and their 13 class-definition FQNs are retired and unsupported. No compatibility
modules remain at those paths. The moved class identities are `ScholarError`,
`ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`, `ScholarDocsError`,
`ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`, `ScholarPolicy`,
`ScholarFabricCitation`, `KnowledgeBundlePayloadV1`, `EnrichmentReportV1`, and `EnrichResultV1`.
This does not establish whether external stored pickles or consumers use an old FQN; that remains
`not_established`. The persisted compatibility surface remains the versioned JSON artifact
contract, whose fields, kind, media type, and schema version are unchanged.
