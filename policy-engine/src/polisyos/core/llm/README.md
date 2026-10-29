# LLM (`polisyos.core.llm`)

`core.llm` provides the traced LLM facade used across PolicyOS. It wraps client calls with
telemetry, cost estimation, response parsing, and retry logic so domain packages can stay thin.

## Role in System

- **Depends on:** `core.observability` for metrics/tracing and `core.resilience` for retry behavior.
- **Used by:** `scientist`, `lex`, and `runtime` when they need model calls.
- **Boundary function:** keeps provider-specific LLM logic out of domain modules.

## Key Concepts

- **Client protocol** - `LLMClientProtocol` standardizes `invoke`, `ainvoke`, and `generate`.
- **Traced client** - `TracedLLMClient` adds spans, token accounting, and callback hooks.
- **Response extraction** - `extract_llm_response_data()` preserves independent known, missing,
  and invalid usage/cost parse states.
- **Cost origin** - producer events distinguish provider-reported, token-estimated, admitted
  reuse, and unknown amounts. Missing or malformed cost is never imputed to zero.
- **Settlement** - `LLMProducerSettlement` binds one producer payload to a local committed,
  unknown, or unmanaged acknowledgment. This does not assert external billing authority.
- **Cache settlement session** - `polisyos.core.llm.cache_settlement` owns opaque cache-flight
  and response-bound reuse capabilities. Scientist reports flight facts through typed handles;
  Core keeps the cache-owner secret, HMAC, and verifier private. A cache marker alone never creates
  admitted reuse.
- **Retry wrapper** - `retry_async` forwards to the shared retry layer.

## Public API

- `LLMClientProtocol`
- `TracedLLMClient`
- `LLMProducerIntent`, `LLMProducerAdmissionGuard`
- `LLMResponseData`
- `extract_llm_response_data`
- `polisyos.core.llm.cache_settlement` exact leaf: `CacheSettlementSession`, opaque handles, and
  exact-client session lookup/creation.
- `estimate_cost`
- `estimate_cost_from_tokens`
- `estimate_cost_from_text`
- `retry_async`

## Current State

- Last updated: 2026-10-09
- The package centers around `protocols.py`, `traced_client.py`, `response.py`, `settlement.py`, `cost.py`, and `retry.py`.
- Token pricing is used only when usage is valid and cost is absent; invalid/missing usage or
  invalid reported cost remains unknown.
- The gateway decoder preserves reported zero, rejects negative/non-finite/malformed cost values,
  and retains a nonzero JSON cost token if binary-float conversion would underflow it to zero.
  Such unrepresentable costs remain invalid/unknown instead of becoming a reported zero.
- Cache reuse is accepted only from the wrapped cache owner's signed in-process provenance.
  A caller-provided cache marker cannot create a reuse event.
- An injected durable producer settlement store records pending before dispatch and commits the
  physical provider outcome once. Cache reuse is a separate zero-amount event linked to its
  provider event. Without a durable store, the acknowledgment remains `unmanaged`.
- Durable event model and logical-route identity come from the pre-dispatch intent. Response-
  declared model/provider labels cannot change the event identity or estimate pricing basis.


### Shared cache lifetime

The exact cache owns the Core settlement session. Each request wrapper is registered
explicitly with `bind_cache_settlement_client`; a mutable application attribute cannot
alias another cache owner. Attestations bind the exact response object and its whole
public dataclass projection to one settled physical origin. `cache_response_projection_bytes`
and `cache_response_digest` own this generic projection; direct flight producers must
use that digest when settling a cacheable result. The separately owned producer settlement
acknowledgment and the local raw cache marker are excluded. A changed usage/model/provider,
raw/tool payload, or body therefore cannot borrow the original proof. Frozen cache entries
and follower snapshots use the same projection. `CacheReuseEvidence.response_digest` retains
the monetary event's text digest; `projection_digest` identifies the whole cache proof.

Completed-flight request state is released after its last live waiter. Retained origins
are bounded independently of a cache adapter: the wrapper's `origin_retention_limit`
defaults to128 entries, while the gateway factory supplies its configured cache size;
producer TTL bounds origin retention. A shared owner's bound may tighten, never widen,
when another wrapper binds it. Native LRU eviction/expiry/clear also removes the matching
origin immediately. A retention miss is a physical cache miss, not an unauthenticated
zero-cost reuse. Existing issued response proofs retain their historical meaning.

Scientist's ledger owns durable cross-run admission. It verifies the live Core response
proof and freezes the configured authorizer scope/epoch, then recomputes the cache key
and both physical/reuse event payloads on reopen. Core does not issue external permission
or replace the configured authorizer.

An admitted runtime job can supply a producer admission guard, bounded begin executor,
and mandatory intent observer to `TracedLLMClient`. The observer receives both the typed
`LLMProducerIntent` and the actual durable begin receipt. Runtime reopens that receipt,
checks its complete pending identity and actual run/attempt against the current owner,
and persists it before dispatch. Expected owner fields cannot replace missing returned
attribution. Current job admission is reselected before and after this operation; no SQL
transaction or factory state mutex spans dependency callbacks.

Factory closure disables admission immediately, including retained clients and model
preflight. Already admitted provider work settles against its original durable intent;
no old lease is reinstated. Runtime's private intent artifact version2.0 retains the actual
begin receipt. The parent attaches the independent refs to the existing Core trace and
closes the basis only after factory admission is disabled. A timed-out/pending observer
leaves the basis explicitly incomplete; it cannot publish a complete monetary projection.
This adds no ledger format or provider invoice authority. Unscoped legacy clients keep
their existing contract.

## Candidate preparation and selected replay quantity

`TracedLLMClient.prepare_producer_input` executes its actual configured
normalization/privacy transform and returns an opaque, instance-owned, single-use
`PreparedLLMInput`. The recorder adds only its source context. Under the actual
producer scope, `prepared_producer_input` reconciles original/prepared hashes,
profile and complete bytes; generate rechecks those bytes before reusing the
transformation. The canonical sanitizer is unchanged. Custom regexes may match
placeholder substrings; a new raw literal equal to a previously issued marker is
still sanitized normally. Strings never substitute for occurrence provenance.

The governed Core facade exports the one usage-quantity parser and capture
observation. It selects one complete source container: malformed non-null nested values are invalid, a nullable container remains
unavailable/missing, partial nested values never borrow outer counts, and supported
top-level fields are considered only when nested usage is absent. A present null
token component stays invalid under the existing Gateway contract. Alias presence
precedence and explicit zero/unknown/invalid survive normal Gateway/Core
settlement. Legacy call-derived counters remain unknown for replay, regardless
of magnitude. Provider origin, billable reuse and actual owner event facts stay
separate; no cache attestation is serialized or borrowed. The existing cost
estimator, settlement owner and tariff are unchanged.

This lifetime guarantee concerns prepared input occurrences, not erasure of all
data in a process. Existing reversible sanitizer maps, real call journals and
caller-held requests/tracebacks retain their own intentional ownership contract.
The preparation client keeps no strong abandoned-handle/raw-snapshot collection.

The same owner projects replay quantities from selected raw component presence,
not nullable normalized DTO counters. `replay_llm_usage_payload` omits absent
fields, normalizes aliases/present values, preserves invalid and never turns a
derived total into a reported field. Its unknown-provenance ceiling only
downgrades availability. Legacy and versioned replay use this one adapter;
qualified quantity/status/total-basis and canonical component presence round-trip.
