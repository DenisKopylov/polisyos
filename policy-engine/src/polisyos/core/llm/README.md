# LLM — трассируемая интеграция и утилиты ответа/стоимости

`core.llm` предоставляет унифицированный слой поверх LLM-клиентов:
протокол клиента, observability-обертку, извлечение usage-данных, оценку стоимости
и совместимый retry facade.

## Состав

```text
llm/
├── protocols.py      # LLMClientProtocol (invoke/ainvoke/generate)
├── traced_client.py  # TracedLLMClient: spans + metrics + cost + observer callback
├── response.py       # extract_llm_response_data() для разных форматов ответа
├── cost.py           # estimate_cost*() через observability.pricing
├── retry.py          # retry_async facade -> core.resilience.retry
└── __init__.py
```

## Роль в системе

- Дает единый интерфейс работы с разными LLM clients.
- Привязывает LLM-вызовы к `run_id`/`model_variant_id` и telemetry pipeline.
- Снижает связность доменных модулей с конкретным провайдером ответа/usage формата.

## TracedLLMClient

`TracedLLMClient` оборачивает `invoke`, `ainvoke`, `generate` и:

- создает `CLIENT` span c атрибутами модели/провайдера/длины промпта;
- собирает `prompt/completion/total tokens`;
- записывает latency и `cost_usd` (из ответа или через fallback estimate);
- пишет метрики через `core.observability.get_metrics()`;
- опционально вызывает `call_observer` без влияния на основной execution path.

## Связи с другими директориями

- `observability/`: tracing, metrics и pricing (`estimate_llm_cost_usd`).
- `resilience/`: `retry_async` делегируется в общий retry policy.
- `scientist/`, `lex/`, `runtime/`: используют этот слой как единый LLM facade.

## Публичный API

- `LLMClientProtocol`
- `TracedLLMClient`
- `LLMResponseData`, `extract_llm_response_data`
- `estimate_cost`, `estimate_cost_from_tokens`, `estimate_cost_from_text`
- `retry_async`
