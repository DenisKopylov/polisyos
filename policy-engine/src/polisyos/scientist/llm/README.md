# LLM Layer: Tracing и monitoring инфраструктура

**OpenTelemetry интеграция для LLM взаимодействий**

LLM layer предоставляет tracing и monitoring для LLM вызовов с унифицированными интерфейсами.

## Структура

```
llm/
└── traced_client.py  # TracedLLMClient с OpenTelemetry
```

## Ключевые компоненты

- **TracedLLMClient**: Wrapper для LLM клиентов с автоматическим tracing
- **OpenTelemetry**: Полная интеграция с observability stack
- **Provider Agnostic**: Поддержка OpenAI, Anthropic, других провайдеров
- **Performance Monitoring**: Latency, token usage, cost tracking

## API Использование

```python
from polisyos.scientist.llm.traced_client import TracedLLMClient

# Создание traced клиента
client = TracedLLMClient(provider="openai", model="gpt-4")

# LLM вызов с автоматическим tracing
response = await client.invoke(prompt="Generate policy draft...")
```

## Связи

- Интегрируется с **agent** layer для LLM-powered agents
- Поддерживает **engine** для workflow observability
- Использует **runtime** для unified tracing