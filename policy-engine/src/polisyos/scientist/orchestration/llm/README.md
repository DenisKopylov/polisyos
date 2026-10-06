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
- **Settlement owner** — `LLMBudgetEnforcer` can compose the actual initialized budget middleware;
  producer event settlement precedes cache publication and carries exact ledger receipts. A raw
  `BudgetState` provides memory accounting, not a durable acknowledgement.
- **Reuse owner** — `create_traced_gateway_client(cache_reuse_authorizer=...)` accepts an internal
  typed deployment-owner contract. External snapshot reuse requires a fresh actor/tenant/scope/
  purpose/exact-evidence/epoch decision. Caller metadata and CAS readability cannot grant reuse.
  Without an owner, snapshot requests invoke the provider. Pure request caching remains scoped
  to the actual principal and trusted accounting composition.

Owner decisions are operational deployment inputs; the library makes no institutional issuer
claim. Cancelled consumers do not cancel owned producer settlement. Failed or missing durable
ACK blocks reuse and remains unknown until exact event receipts reconcile; process death before
a provider completion/event is observed requires external provider evidence.

The factory explicitly binds the actual `CachingLLMClient` emitter to its traced receiver.
Manual trusted compositions pass that client's `cache_reuse_owner`; an unconfigured receiver
and bare response parser bill provider usage. The runtime issuer record authenticates the exact
request, cache key and reuse event. Another cache's issuer or copied/edited prior record cannot
grant reuse; provider/request kwargs do not install receiver authority. This operational issuer
binding is separate from the deployment owner's permission decision above and cannot be serialized.

Each eligible cache flight owns one absolute monotonic deadline through provider I/O,
mandatory completion, serialization and publication. An observed late response is still
settled; expiry refuses result/cache admission after settlement. Physical completion can
outlive that deadline when a provider or synchronous accounting/cache lock cannot stop.
Followers share the producer deadline. Cache reads recheck the supplied owner decision
before emission; custom caches must implement `put(..., admission_check=...)` at their
atomic storage boundary. An unsupported signature refuses before provider work starts.
Atomic publication is verified here for `InMemoryPromptCache`; a foreign implementation
requires its own conformance evidence. The owner decision itself remains a deployment
premise, including any required atomic epoch semantics.

## Public API

- `GatewayLLMClient`, `GatewayLLMResponse`, `GatewayUsage`
- `GatewayLLMConfig`
- `TracedLLMClient`, `LLMClientProtocol`
- `create_traced_gateway_client(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 14
- Exports: 7
- README теперь отражает profiles/fallback/cache surface, а не только gateway client
