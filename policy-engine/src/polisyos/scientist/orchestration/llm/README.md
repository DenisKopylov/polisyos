# LLM (`polisyos.scientist.llm`)

`llm` is Scientist's gateway-first LLM runtime: client configuration, traced
execution, fallback routing, prompt caching, and registry model profiles for control/UI surfaces.

## Role in the system

- **Depends on:** `core.llm`, `core.observability`
- **Used by:** `scientist.agent`, runtime control flows, and multi-model orchestration
- The package isolates provider/gateway specifics from agent- and workflow-layer code.

## Key concepts

- **GatewayLLMClient** — OpenAI-compatible gateway transport.
- **GatewayLLMConfig** — env-driven runtime configuration.
- **TracedLLMClient** — observability-aware wrapper around the raw client.
- **Profiles registry** — built-in model profiles for runtime selection/UI.
- **Fallback router / prompt cache** — supporting runtime resilience and efficiency.
- **Producer settlement** — the traced cache/gateway path retains provider intent and terminal
  monetary status; authenticated cache reuse is recorded separately from physical provider work.
  Durable event model and route identity remain bound to the configured pre-dispatch intent, not
  response-declared labels.
- **Execution-plan persistence** — `persist_execution_plan()` returns the exact manifest profile
  selected by its CAS write. This preserves the producer's selected view for downstream source
  graphs; it does not infer a method-catalog choice or an HTE semantic binding.

## Public API

- `GatewayLLMClient`, `GatewayLLMResponse`, `GatewayUsage`
- `GatewayLLMConfig`
- `TracedLLMClient`, `LLMClientProtocol`
- `create_traced_gateway_client(...)`
- `prompt_cache.PreparedCacheRequest`, `prompt_cache.prepare_cached_request(...)`
- `prepared_request.PreparedCallValues`, `prepared_request.prepare_call_values(...)`

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-09
- The README now covers the profiles/fallback/cache surface, not only the gateway client.
- LLM cost events retain reported/estimated/reuse/unknown origin, nullable amount, producer
  identity, and settlement acknowledgment. Scope-bound prompt reuse requires an authorizer;
  ordinary uncached provider calls remain supported.
- The gateway factory accepts an injected durable producer settlement store. Ordinary
  `ControlPlaneService` NL runs use the app-scoped `FileBudgetLedger` at
  `core_runs_root/.runtime/llm-cost-ledger.json`, unless a typed store override is supplied.
  Each run uses `nl-run:{run_id}` as its producer accounting key; this records observed events
  without adding a spend limit. NL compiler/preflight calls and model-variant calls retain their
  per-call events in run state and the agents read surface. Local settlement acknowledges only
  local ledger state; it does not assert provider invoices or external billing authority.


For a selected method-metric compile, the existing typed ExecutionPlan is persisted
with exactly one policy_candidate input binding the selected Trinity candidate and
its manifest profile. The optional request-version 1.2 bridge preserves that exact
plan ref into compilation; absent legacy refs retain prior behavior. Method return
slots are retained as plan declarations and fresh consumers recompute the selected
plan/registry join. LLM method choice remains candidate intent and does not confer
execution authority or scientific appropriateness.


Configured runtime prompt caches live with the application; provider/traced wrappers and
settlement hooks remain request-local. Shared cache flights use one concurrent result
across request event loops, and followers consume an immutable snapshot of their exact
flight rather than whichever entry is currently at the cache head. No-key and explicit
zero-size/zero-TTL modes remain uncached. `GatewayLLMConfig.cache_maxsize` also bounds
retained Core origins; legacy get/put-only adapters cannot cause unbounded Core history.
The current authorizer still runs for every candidate reuse, including cache hits.

Ordinary NL jobs bind every factory-created client to the admitted job's run, producer
ledger, and request-local cache dependencies. The current job creation envelope and
running lease are reselected around each hit admission and durable producer begin,
independently of the snapshot authorizer's decision. The snapshot authorizer remains a restrictive integration input;
local accounting does not certify an institution's permission or a provider invoice.
Copied task/thread contexts retain this binding, and closing the job scope prevents
retained clients from starting further work. Already begun work retains its original
intent/attempt through settlement. Missing snapshot reuse facts allow a physical call
only while the separate current job admission is established; a closed scope, lease
failure, guard timeout or unavailable control store refuses new dispatch.

Cache eligibility requires explicit numeric zero temperature or the existing exact
deterministic simulator implementation. Omitted external-provider sampling defaults,
tool calls, strict independent seeds, and explicit disabled-cache modes remain uncached.
Private cache selectors participate in identity but are never added to provider wire
metadata; caller-selected metadata keeps its existing wire contract. Every emitted hit,
including values from custom get/put adapters and shared followers, requires Core's exact
whole-response-projection and retained-origin proof. The gateway uses the same actual
prepared immutable request for transport and cache identity. Preparation detaches the
complete caller values, transport URL/headers, provider configuration and exact JSON body
before keying or scheduling dispatch. All caller wire fields, including nested timestamp-like
names and cache busters, remain in identity. Only the gateway's own generated retry nonce
is neutral; an explicit caller idempotency header remains bound.

Fallback preparation selects the currently available head endpoint and freezes its
ordered physical plan. Success from a later endpoint or response-format negotiation
that changed the successful payload is physical-only: it cannot fill the original head's
cache entry or provide a shared follower proof. Recovery selects the current head again;
an old secondary answer cannot stand in for a recovered primary request. A provider with
no prepared call contract is physical-only. The built-in deterministic simulator also
freezes its response-producing configuration. Native wire values must already be projected
by their typed owner: raw datetime/model/unknown values and nonfinite JSON numbers are
rejected, never coerced through `default=str`. A cache publication racing admission may
degrade to uncached work; this path does not claim minimal provider work for that race.

Fresh job status and the agents/debug view reconcile cost events with the same durable
ledger payload and current owning attempt. Fresh job status additionally joins the exact
V3 proposal/profile to the terminal Core output and checks V3's Core run/attempt. It
reopens the independent central-begin intent set persisted in that Core trace, including
factory aliases without a proposal observer. Missing/extra/changed ledger rows withhold
the projection. Historical jobs without this basis are explicitly limited. These are
central producer outcomes; transport retry/network invoice completeness is not asserted.
Stored completion progress and candidate-only limitation statuses remain unchanged.

Configured logical provider route is part of the cache identity, alongside model and
request parameters. A route change produces a physical miss. The traced owner's
explicit route configuration wins at durable begin; response-declared provider labels
cannot rewrite physical event identity or turn a later reuse into a different route.

Factory admission uses short state tickets. Timed-out or queued dependency callbacks
cannot return a dispatch authorization after closure. Closure never waits for those
workers. The budget middleware's active binding registry has a separate short lock from
monetary dependency I/O, so releasing a binding also does not wait for an in-progress
ledger begin/readback. Actual durable begins retain the binding/attempt captured before
I/O; late pending receipts are not copied into a new owner or falsely committed.

A running blocking dependency thread cannot be forcibly stopped by the existing
`BlockingDependencyGuard`; `Future.cancel()` only cancels work that has not started.
Such work may occupy its bounded worker or the dependency's own I/O mutex until it
returns. This is a declared dependency-cancellation limitation, not dispatch permission:
factory/binding/trace closure remains independent, late admission is refused, and an
incomplete source basis withholds authoritative monetary projection. Transport retries
and model catalog requests remain outside the central producer cost completeness claim.

Provider preflight uses that same prepared-cache contract. The immutable plan contains
one actual gateway preparation and the cache owner's digest, and binds once to one fresh
wrapper for one logical call. Its native/control tree is immutable; callers receive
copies. Generation verifies the complete caller identity and consumes the same plan,
including on a hit. Live scoped clients retain their separate current-admission and
private-selector injection path; pre-bound ordinary plans cannot bypass that path.

The preflight adapter delegates preparation and successful dispatch identity to its real
gateway. It does not declare an opaque provider reusable. The retained preflight table
holds the cache resource and durable producer reference, keyed by the current complete
request digest in addition to run/owner/provider scope. Each invocation has fresh gateway,
cache and traced wrappers and local settlement hooks. Retained ledger/origin validation
still runs before network checks; changed wire/transport selects another resource, while
missing or altered durable origin fails closed. A negotiated plain response cannot warm
a requested-format origin. Cache entries and local proof sessions remain process-local;
ledger formats and their historical readers do not change.

A preflight adapter closes unused/hit clients and closes physical clients after their
executor terminates. Cancelling a waiter disables new work but defers closing an admitted
physical gateway until it settles, preserving the actual run/attempt receipt. This does
not add provider I/O interruption, invoice authority or catalog-call accounting. The
actual provider-verification loopback module and research POST pre-admission module are
required consumers in the deciding test wave, with the preparation/reuse bridge removed
as a separate behavioral falsifier. Those native/removal checks remain unrun in proposals.


Prepared-call equality has a separate lossless Python-value representation. It
retains explicit native type tags, raw bytes, finite float bit-significant values
(including signed zero), and dictionary order. It never asks the evidence/cache
normalizer to decide whether two invocations are equal. A valid snapshot A and
changed bytes B with A's unchanged declared hash are different inputs in both
directions. Input mismatch refuses before authorization, producer begin or wire
execution; an unchanged input may still use the independent current owner and
origin checks. The existing positional/named prompt equivalence is unchanged.

Exact native tuples remain tuples and lists remain lists at Python prepared
providers. Gateway owns its separate strict HTTP JSON projection, where supported
sequences become JSON arrays and raw unknown objects/nonfinite numbers refuse.
Aliases/cycles, views, subclasses, nonfinite Python values and opaque objects do
not acquire a native equality claim. They remain supported physical-only Python
calls with original nested objects and without serialization or copying hooks;
no pre-bound ordinary plan may substitute them. The physical-call token identifies
that admission/event, not a proven immutable payload. Existing live job and actual
producer-begin admission still precedes every physical executor. Opaque adapters
never become reusable merely by using this helper. Known prepared providers and
the simulator propagate the actual native snapshot's reusability.

Configured durable settlement snapshots that fail decoding or validation withhold
provider preflight as the existing typed `unknown` result before catalog/network
checks. They do not establish a failed provider call. An absent, unreadable or
unconfigured settlement store retains its setup-failure behavior; no amount,
provider authority or accounting completeness is inferred. The existing
`test_provider_preflight_records_bound_gateway_completion_and_reuses_exact_event`
variants pin altered durable-origin refusal. Its Cloud result is source-bound;
local composition, the remaining Runtime fixture failures and the third
preparation/reuse removal remain separate verification obligations.

## Source-owned N4 preparation and emission

The actual draft, multipass/consolidation, formalizer and critic owners supply
stages from control flow. The generic common carrier knows none of this stage
vocabulary. Scientist exposes exact owner aliases through its existing facade;
Gateway consumes the governed common/Core boundaries. No private cross-package
import exception or deep-import ratchet is added.

The recorder receives an opaque prepared-input occurrence from its actual stock
Core client, then binds source/prepared hashes and the configured transformation
profile. Core consumes one atomic actual generate permit under the active source scope.
The client weakly tracks pending opaque inputs; the request/coroutine carries the
handle without a recorder-owned strong map or serialized raw source snapshot.
Recorder removes that local carrier before any prompt/context/wire processing.
The original sanitizer handles every new raw input, even text equal to a previous
marker; unsupported custom client transformations remain unqualified. Gateway
checks the complete actual call and an immutable prepared-emission obligation
at send. The existing JSON-mode fallback changes only `response_format`.

Trace request digests, body seals, prepared dispatch identities and call hashes
remain distinct quantities. None establishes external issuer authority, law,
permission, currentness or historical billing.
