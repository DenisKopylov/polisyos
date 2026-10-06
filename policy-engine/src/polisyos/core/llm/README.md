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
