# LLM Layer (`polisyos.scientist.llm`)

`llm` — gateway-first LLM слой Scientist с trace-совместимым клиентом и registry профилей моделей.

## Роль

- дает легковесный OpenAI-compatible gateway client (`GatewayLLMClient`);
- оборачивает raw client в traced клиент (`TracedLLMClient` из `core.llm`);
- читает env-конфиг gateway и создает runtime client фабрикой;
- хранит список доступных модельных профилей для runtime control/UI.

## Ключевые файлы

- `gateway_client.py` — async `/chat/completions` клиент + retry/timeout + usage parsing.
- `factory.py` — `GatewayLLMConfig.from_env()` и `create_traced_gateway_client()`.
- `traced_client.py` — compatibility bridge к `polisyos.core.llm.traced_client`.
- `profiles/models.py` — модель `ModelProfile`.
- `profiles/registry.py` — singleton `ModelProfileRegistry`.
- `profiles/builtin_profiles.py` — встроенные профили (OpenAI/Anthropic/Gemini/Groq/Gonka через gateway).

## Runtime env

Основные переменные:
- `POLISYOS_LLM_GATEWAY_BASE_URL`
- `POLISYOS_LLM_GATEWAY_API_KEY`
- `POLISYOS_LLM_GATEWAY_TIMEOUT_S`
- `POLISYOS_LLM_GATEWAY_MAX_RETRIES`
- `POLISYOS_LLM_GATEWAY_PROVIDER`
- `POLISYOS_LLM_CAPTURE_PROMPT`
- `POLISYOS_LLM_MAX_PROMPT_CAPTURE_CHARS`

Если `POLISYOS_LLM_GATEWAY_BASE_URL` не задан, `create_traced_gateway_client()` возвращает `None` (вызывающий код решает fallback).

## Связи

- `agent/*` использует traced LLM-клиенты из этого слоя.
- runtime control API использует model profiles для multi-model запусков.
- observability/token-cost метрики пишутся через `TracedLLMClient`/`core.observability`.
