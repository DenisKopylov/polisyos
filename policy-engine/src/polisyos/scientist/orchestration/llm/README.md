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

## Точный numeric ingress и cost observer

Gateway completion JSON сохраняет дробные numeric tokens через `Decimal` до проверки
cost evidence. Ненулевой `1e-1000` нельзя выдать за reported zero после float underflow;
negative и невалидная стоимость остаются invalid. Traced callback передаёт amount,
cost/usage statuses и origin существующему runtime cost consumer. Unknown cost не
становится нулём, а estimate остаётся отличим от reported amount.

Prompt cache и factory используют completion provenance того же producer: обычный hit
отражается как reuse без нового provider call. A observer composition сохраняет
unmanaged settlement; отдельная protected/durable budget integration этим не доказана.
