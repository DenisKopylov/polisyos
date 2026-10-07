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

## Cost observation and completion provenance

The response and traced-client owners distinguish reported cost, a token-based estimate,
unknown cost, and invalid numeric input. A missing reported amount can be estimated only
from usable token evidence; an invalid reported amount stays invalid. Explicit reported
zero remains zero. Call observers receive the status and origin together with the amount.

`settlement.py` carries producer completion and cache provenance through these owners.
The ordinary A runtime observer path has no trusted settlement owner and records
`settlement_status="unmanaged"`. Its operational cost projection does not establish an
invoice or protected budget settlement. The cache and factory must use the same producer
contract so reuse is distinguished from another provider call.
