# LLM (`polisyos.scientist.llm`)

`llm` — gateway-first LLM runtime Scientist: конфигурирование клиентов, traced
execution, fallback routing, prompt caching и registry model profiles для control/UI surfaces.

## Роль в системе

- **Зависит от:** `core.llm`, `core.observability`
- **Используется в:** `scientist.agent`, runtime control flows, multi-model orchestration
- Пакет изолирует provider/gateway specifics от agent- и workflow-layer кода.

## Ключевые концепции

- **GatewayLLMClient** — OpenAI-compatible gateway transport.
- **GatewayLLMConfig** — env-driven runtime configuration.
- **TracedLLMClient** — observability-aware wrapper поверх raw client.
- **Profiles registry** — built-in model profiles for runtime selection/UI.
- **Fallback router / prompt cache** — supporting runtime resilience and efficiency.
- **Producer settlement** — the traced cache/gateway path retains provider intent and terminal
  monetary status; authenticated cache reuse is recorded separately from physical provider work.
  Durable event model and route identity remain bound to the configured pre-dispatch intent, not
  response-declared labels.

## Public API

- `GatewayLLMClient`, `GatewayLLMResponse`, `GatewayUsage`
- `GatewayLLMConfig`
- `TracedLLMClient`, `LLMClientProtocol`
- `create_traced_gateway_client(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-10-09
- Python modules: 14
- Exports: 7
- README теперь отражает profiles/fallback/cache surface, а не только gateway client
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
