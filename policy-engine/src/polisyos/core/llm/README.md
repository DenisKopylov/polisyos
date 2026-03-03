# LLM — traced facade для LLM-вызовов

`core.llm` дает единый адаптер над LLM-клиентами: протокол клиента, telemetry wrapper, извлечение usage, cost estimation и retry.

## Состав

```text
llm/
├── protocols.py     # LLMClientProtocol (invoke/ainvoke/generate)
├── traced_client.py # TracedLLMClient (span/metrics/cost/callback)
├── response.py      # extract_llm_response_data()
├── cost.py          # estimate_cost* wrappers
└── retry.py         # retry_async facade -> core.resilience.retry
```

## TracedLLMClient

`TracedLLMClient` оборачивает `invoke`, `ainvoke`, `generate` и:
- создает `CLIENT` span с атрибутами модели/провайдера;
- считает latency и токены (`prompt/completion/total`);
- пишет стоимость (`cost_usd`) из ответа или через pricing fallback;
- записывает метрики через `core.observability.get_metrics()`;
- опционально вызывает `call_observer` (без влияния на основной execution path).

## Где используется

- `scientist`, `lex`, `runtime` как единый вход для LLM-взаимодействий.
- `observability` как источник трасс и cost telemetry.
- `resilience` как общий retry policy.

## Публичный API

- `LLMClientProtocol`
- `TracedLLMClient`
- `LLMResponseData`, `extract_llm_response_data`
- `estimate_cost`, `estimate_cost_from_tokens`, `estimate_cost_from_text`
- `retry_async`
