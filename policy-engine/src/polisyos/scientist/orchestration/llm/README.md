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

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-09
- Python modules: 14
- Exports: 7
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
