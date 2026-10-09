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
