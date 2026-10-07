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
- **Response extraction** - `extract_llm_response_data()` normalizes usage/response metadata.
- **Producer settlement** - internal `settlement.py` binds an observed provider completion to
  an immutable event and its actual accounting acknowledgement. Trusted wrapper composition
  installs the completion hook; provider kwargs cannot install an accounting owner.
- **Cost estimation** - helper functions estimate pricing from tokens or raw text.
- **Retry wrapper** - `retry_async` forwards to the shared retry layer.

## Public API

- `LLMClientProtocol`
- `TracedLLMClient`
- `LLMResponseData`
- `extract_llm_response_data`
- `estimate_cost`
- `estimate_cost_from_tokens`
- `estimate_cost_from_text`
- `retry_async`

## Current State

- Last updated: 2026-04-03
- The package still centers around `protocols.py`, `traced_client.py`, `response.py`, `cost.py`, and `retry.py`.
- Cost telemetry falls back to shared pricing defaults when provider responses omit pricing data.
- Asynchronous generate/ainvoke completion remains owned after initiating caller cancellation. Optional
  telemetry is isolated from required accounting. An absent durable acknowledgement is unknown,
  and cannot publish a reusable provider result. Durable budget composition is supplied by the
  Scientist budget owner; a plain traced client only records an unmanaged operational event.
- A failed mandatory `required_accounting` callback retains its exact observed event and
  blocks new provider calls. `reconcile_accounting(event_identity)` redelivers only that frozen
  payload to the same trusted callback. A callback's successful return confirms local delivery;
  its owner must deduplicate ambiguous prior effects. This legacy callback is not a durable
  ledger acknowledgement; the initialized budget middleware supplies that separate capability.
- Cache reuse requires a receiver-admitted issuer: the factory or trusted manual composition
  supplies the exact cache client's runtime owner to `TracedLLMClient(cache_reuse_owner=...)`.
  The default is no issuer; bare extraction and an unconfigured receiver treat responses as
  provider completions. Issuer records authenticate the exact request, cache key and reuse event;
  foreign issuers, borrowed requests and altered keys cannot grant zero-charge reuse. Request
  kwargs, names, module suffixes, private flags and copied mappings cannot configure the receiver.
  It is an in-process contract between trusted components,
  not serialized permission or protection against arbitrary code with access to process memory.
  Known physical provider completion is always a provider event, even if its response borrows
  authentic prior cache provenance; actual cache emission remains a separate zero-extra-charge
  consumption event.

## Canonical B1.2 completion profile

Response extraction distinguishes observed valid usage/cost from missing or invalid fields.
Numeric telemetry defaults remain available, but absent counts do not establish zero usage.
Reported zero and valid observed counts priced at a configured zero rate remain valid amounts.
An invalid reported cost cannot fall back to token pricing. Inaccessible usage/cost metadata
preserves an obtained response with unknown monetary evidence.

- Producer events carry `amount=None`/`cost_origin="unknown"` when monetary evidence is missing
  or invalid. Such an event cannot acquire a committed settlement or reusable cache publication.
  Optional metrics can still report numeric token defaults; they do not establish a charge.
  Trusted accounting composition fixes the attempt and request identity before provider entry.
- The supported accounting ports are `generate`, `invoke` and `ainvoke`. Delegated
  `generate_stream` has no settlement contract and refuses before provider entry when required
  accounting or an active settlement owner is configured. Unmanaged streaming remains delegated.
- `TracedLLMClient.with_model(model_name)` preserves the same client for the same model and
  refuses a protected model change without an owner-transfer contract. Unmanaged views retain
  tracing configuration; callers cannot unwrap away a pending accounting owner during normalization.

The actual configured cache emitter records each request's opaque runtime registration before
physical dispatch or joining a flight. Its terminal report binds that receiver's request, owner
scope and attempt to the actual producer identity and original settlement or error. A joined
receiver can retire only its own undispatched budget intent; denied result admission does not
erase a known physical charge or turn the producer's unknown amount into zero. These internal
registrations are not serialized permission or financial authority.
The exact configured traced wrapper also reports preflight versus delegation. A refusal before
delegation cannot manufacture a new provider event from an older pending accounting response;
failure after entering a foreign provider remains unknown without exact completion evidence.
