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
