# LLM Layer: Tracing и Monitoring для LLM взаимодействий

**Инфраструктура для мониторинга, трассировки и отладки взаимодействий с LLM**

LLM Layer предоставляет унифицированный интерфейс для работы с различными LLM провайдерами с автоматической трассировкой через OpenTelemetry и сбором метрик производительности.

## Обзор

Папка `llm/` содержит инфраструктуру для observability LLM взаимодействий в Scientist системе. Основной компонент - `TracedLLMClient` - wrapper, который автоматически добавляет tracing и metrics ко всем LLM вызовам.

## Архитектура

```
llm/
├── __init__.py              # Экспорт TracedLLMClient
└── traced_client.py         # TracedLLMClient с OpenTelemetry интеграцией
```

## Компоненты

### 🤖 TracedLLMClient (traced_client.py)

Универсальный wrapper для LLM клиентов с автоматической observability:

#### Основные возможности

- **OpenTelemetry Tracing**: Создание CLIENT spans для каждого LLM вызова с метаданными модели и промпта
- **Metrics Collection**: Автоматический сбор метрик по использованию токенов (prompt/completion)
- **Error Handling**: Корректная обработка ошибок с записью в spans и metrics
- **Provider Detection**: Автоматическое определение провайдера (OpenAI, Anthropic, Mock)
- **Protocol Support**: Поддержка различных интерфейсов LLM клиентов через `LLMClientProtocol`

#### LLMClientProtocol

Протокол для совместимых LLM клиентов:

```python
@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM clients that can be wrapped."""

    async def generate(self, **kwargs: Any) -> Any:
        """Async generation method."""

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        """Sync invoke method."""

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        """Async invoke method."""
```

#### Конструктор TracedLLMClient

```python
class TracedLLMClient:
    def __init__(
        self,
        client: Any,                           # Underlying LLM client
        model_name: str | None = None,         # Override model name detection
        capture_prompt: bool = False,          # Include prompt in traces (privacy consideration)
        max_prompt_length: int = 200,          # Max prompt length for traces
    ) -> None:
        # Auto-detects model name and provider from client
```

#### Методы

##### invoke() - Synchronous вызов

```python
def invoke(self, prompt: str, **kwargs: Any) -> Any:
    """Synchronous LLM call with tracing."""
    # Creates span: f"llm.invoke.{model_name}"
    # Records token usage and call status
    # Returns original response
```

##### ainvoke() - Asynchronous вызов

```python
async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
    """Asynchronous LLM call with tracing."""
    # Creates span: f"llm.ainvoke.{model_name}"
    # Records token usage and call status
    # Returns original response
```

##### generate() - Универсальный метод

```python
async def generate(self, *args: Any, **kwargs: Any) -> Any:
    """Universal generation method with tracing."""
    # Handles both sync and async underlying clients
    # Creates span: f"llm.generate.{model_name}"
    # Auto-detects prompt from various parameter formats
```

#### Tracing Attributes

Каждый span содержит следующие атрибуты:

```python
{
    "polisyos.llm.model": "gpt-4",           # Model name
    "polisyos.llm.provider": "openai",       # Provider (openai/anthropic/mock)
    "polisyos.llm.prompt_length": 150,       # Prompt length in characters
    "polisyos.llm.tokens.prompt": 45,        # Prompt tokens used
    "polisyos.llm.tokens.completion": 120,   # Completion tokens used
    "polisyos.llm.tokens.total": 165,        # Total tokens used
    # Optional: "polisyos.llm.prompt_preview": "..."  # If capture_prompt=True
}
```

#### Metrics Collection

Интеграция с MetricsRegistry для сбора статистики:

- **Call Count**: Количество вызовов по моделям и статусам
- **Token Usage**: Суммарное использование токенов prompt/completion
- **Error Rate**: Процент ошибок по моделям

#### Автоматическое обнаружение

##### Model Name Detection

```python
def _detect_model_name(self) -> str:
    """Auto-detect model name from client attributes."""
    for attr in ("model_name", "model", "model_id"):
        value = getattr(self._client, attr, None)
        if value:
            return str(value)
    return "unknown"
```

##### Provider Detection

```python
def _detect_provider(self) -> str:
    """Auto-detect provider from client class name."""
    client_type = type(self._client).__name__.lower()
    if "openai" in client_type:
        return "openai"
    if "anthropic" in client_type:
        return "anthropic"
    if "mock" in client_type:
        return "mock"
    return "unknown"
```

#### Token Usage Extraction

Поддержка различных форматов ответов LLM:

```python
def _extract_token_usage(self, response: Any) -> tuple[int, int]:
    """Extract token counts from various response formats."""
    # OpenAI format: response.usage.prompt_tokens/completion_tokens
    # Anthropic format: response.input_tokens/output_tokens
    # Dict format: response["usage"]["prompt_tokens"]
    # Returns: (prompt_tokens, completion_tokens)
```

## API Использование

### Базовое использование

```python
from polisyos.scientist.llm import TracedLLMClient
import openai

# Создание traced клиента
client = openai.OpenAI()
traced_client = TracedLLMClient(client, capture_prompt=False)

# Использование как обычного клиента
response = traced_client.invoke(
    prompt="Explain quantum computing",
    model="gpt-4",
    temperature=0.7
)

# Все вызовы автоматически трассируются
```

### Async использование

```python
# Async вызовы
response = await traced_client.ainvoke(
    prompt="Write a haiku about AI",
    model="gpt-4"
)
```

### С включением промпта в traces

```python
# Для отладки (учитывать privacy!)
traced_client = TracedLLMClient(
    client,
    capture_prompt=True,
    max_prompt_length=500
)

response = traced_client.invoke("Sensitive prompt...")
# Промпт будет включен в span attributes (truncated)
```

### Интеграция с различными провайдерами

```python
# OpenAI
openai_client = TracedLLMClient(openai.OpenAI())

# Anthropic
anthropic_client = TracedLLMClient(anthropic.Anthropic())

# Mock для тестирования
mock_client = TracedLLMClient(MockLLM())
```

### Использование в Agent Layer

```python
from polisyos.scientist.agent.drafter import LLMDrafterAgent
from polisyos.scientist.llm import TracedLLMClient

# Создание traced клиента
traced_llm = TracedLLMClient(openai.OpenAI())

# Передача в агент
drafter_agent = LLMDrafterAgent(llm_client=traced_llm)

# Все LLM вызовы агента будут автоматически трассироваться
draft = await drafter_agent.draft(problem_frame, context={})
```

## Tracing и Observability

### Span Hierarchy

```
experiment.workflow (root span)
├── llm.invoke.gpt-4 (CLIENT span)
│   ├── polisyos.llm.model: gpt-4
│   ├── polisyos.llm.provider: openai
│   ├── polisyos.llm.tokens.prompt: 45
│   └── polisyos.llm.tokens.completion: 120
└── llm.ainvoke.claude-3 (CLIENT span)
    ├── polisyos.llm.model: claude-3
    ├── polisyos.llm.provider: anthropic
    └── ...
```

### Metrics Dashboard

TracedLLMClient интегрируется с MetricsRegistry для создания дашбордов:

- **LLM Call Volume**: Количество вызовов по моделям и провайдерам
- **Token Consumption**: Тренды использования токенов
- **Error Rates**: Процент неудачных вызовов
- **Latency**: Время отклика по моделям
- **Cost Tracking**: Оценка затрат на основе token usage

### Отладка и Troubleshooting

#### Поиск проблемных вызовов

```python
# В traces найти spans с ошибками
# polisyos.llm.* attributes помогут идентифицировать:
# - Какую модель вызывали
# - Какой промпт использовали (если capture_prompt=True)
# - Сколько токенов потратили
# - Какой статус вызова (success/error)
```

#### Мониторинг производительности

```python
# Metrics покажут:
# - Наиболее используемые модели
# - Тренды token consumption
# - Rate limits и throttling
# - Cost patterns
```

## Конфигурация и настройки

### Environment Variables

```bash
# OpenTelemetry настройки (через core observability)
OTEL_SERVICE_NAME=policy-engine
OTEL_TRACES_EXPORTER=console  # Для development

# Metrics backend
POLISYOS_METRICS_BACKEND=prometheus
```

### Privacy Considerations

```python
# В production отключить capture_prompt
traced_client = TracedLLMClient(
    client,
    capture_prompt=False  # Не логировать промпты
)

# Использовать только в development/debugging
debug_client = TracedLLMClient(
    client,
    capture_prompt=True,
    max_prompt_length=1000
)
```

## Тестирование

### Unit тесты

```bash
# Тестирование traced клиента
pytest tests/scientist/test_llm_*.py -v

# Конкретные компоненты
pytest tests/scientist/test_llm_traced_client.py -v
```

### Mock тестирование

```python
from polisyos.scientist.agent.drafter import MockLLM

# Использование mock клиента для тестирования
mock_llm = MockLLM()
traced_mock = TracedLLMClient(mock_llm)

# Все tracing работает, но без реальных API вызовов
response = traced_mock.invoke("Test prompt")
```

### Test Coverage

- **TracedLLMClient**: Основная функциональность tracing и metrics
- **Protocol Support**: LLMClientProtocol совместимость
- **Provider Detection**: Автоматическое обнаружение провайдеров
- **Token Extraction**: Парсинг различных форматов ответов
- **Error Handling**: Корректная обработка исключений
- **Async Support**: Синхронные и асинхронные вызовы

## Расширение

### Кастомные LLM клиенты

```python
class CustomLLMClient:
    """Кастомный LLM клиент."""

    def invoke(self, prompt: str, **kwargs) -> dict:
        # Кастомная логика
        return {"response": "answer", "usage": {"prompt_tokens": 10, "completion_tokens": 20}}

    async def ainvoke(self, prompt: str, **kwargs) -> dict:
        # Async версия
        return await self._call_api(prompt, **kwargs)

# Автоматически совместим с TracedLLMClient
traced_custom = TracedLLMClient(CustomLLMClient())
```

### Кастомная token extraction

```python
class CustomTracedClient(TracedLLMClient):
    """Расширенный клиент с кастомной token extraction."""

    def _extract_token_usage(self, response: Any) -> tuple[int, int]:
        # Кастомная логика для специфического API
        if hasattr(response, "custom_usage"):
            return response.custom_usage.prompt, response.custom_usage.completion
        return super()._extract_token_usage(response)
```

### Дополнительные metrics

```python
class MetricsTracedClient(TracedLLMClient):
    """Клиент с дополнительными метриками."""

    def _record_tokens(self, span, metrics, prompt_tokens, completion_tokens, status):
        # Стандартные метрики
        super()._record_tokens(span, metrics, prompt_tokens, completion_tokens, status)

        # Дополнительные кастомные метрики
        span.set_attribute("custom.cost_estimate", self._calculate_cost(prompt_tokens, completion_tokens))
        span.set_attribute("custom.efficiency", completion_tokens / max(prompt_tokens, 1))
```

## Связанные компоненты

- **Core Observability**: `get_tracer()`, `get_metrics()` для tracing и metrics
- **Agent Layer**: Все LLM агенты используют TracedLLMClient для мониторинга
- **Orchestrator**: Workflow nodes логируют LLM вызовы через timeline events
- **Runtime**: Integration с experiment lifecycle для cost tracking

## Troubleshooting

### Нет traces от LLM вызовов

```
Проверьте:
- Правильно ли инициализирован TracedLLMClient
- Настроен ли OpenTelemetry tracer
- Используется ли traced клиент вместо прямого
```

### Неправильное обнаружение модели

```
Решение: Передайте model_name явно в конструктор
traced_client = TracedLLMClient(client, model_name="gpt-4-turbo")
```

### Token usage не записывается

```
Проверьте:
- Поддерживает ли LLM API usage statistics
- Корректно ли реализована _extract_token_usage для вашего провайдера
- Правильно ли настроены metrics
```

### Performance impact

```
TracedLLMClient добавляет минимальный overhead (~1-2ms per call)
Для high-throughput сценариев рассмотрите batch tracing или sampling
```

## Будущие улучшения

### 🚀 Планируемые возможности

- **Cost Tracking**: Автоматический расчет стоимости на основе token usage и тарифов провайдеров
- **Response Caching**: Интеллектуальное кеширование ответов для снижения API calls
- **Load Balancing**: Автоматическое распределение нагрузки между моделями/провайдерами
- **Fallback Logic**: Graceful degradation при недоступности primary модели
- **Advanced Metrics**: Response quality scores, latency percentiles, error classification

### 🔬 Продвинутые возможности

- **Prompt Engineering Tracking**: Анализ эффективности различных промптов
- **Model Comparison**: A/B testing различных моделей и настроек
- **Usage Quotas**: Управление лимитами использования по пользователям/проектам
- **Audit Trail**: Полная история всех LLM взаимодействий для compliance