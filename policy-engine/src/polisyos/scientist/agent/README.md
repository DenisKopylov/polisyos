# Agent Layer: LLM Агенты и Промпты

**Слой генерации политик через LLM и эвристические агенты**

Agent Layer отвечает за генерацию и принятие решений о политиках через различные стратегии: от простых эвристических агентов до продвинутых LLM-based систем.

## Обзор

Папка `agent/` содержит компоненты для генерации экономических политик из естественного языка пользователя. Включает как production-ready LLM интеграции, так и mock компоненты для тестирования.

## Архитектура

```
agent/
├── __init__.py           # Экспорт основных классов
├── base.py               # Абстрактный BaseAgent и MockAgent
├── drafter.py            # LLM-based генерация политик
├── prompts.py            # Системные промпты для LLM
└── prompt.py             # Альтернативные промпты
```

## Компоненты

### 🤖 BaseAgent (base.py)

Абстрактный базовый класс для всех агентов принятия решений:

```python
class BaseAgent(ABC):
    @abstractmethod
    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        """Принимает данные (DataFrame), возвращает Решение (IR)."""
        pass
```

#### MockAgent

Простой эвристический агент для тестирования без LLM зависимостей:

- **Логика**: Анализирует безработицу и бюджетный баланс
- **Высокая безработица** → Агрессивные субсидии (rate=0.20)
- **Низкая безработица** → Умеренные субсидии (rate=0.10)
- **Первый шаг** → Налоги для сбора доходов (income_tax, rate=0.15)

```python
class MockAgent(BaseAgent):
    """Притворяется LLM. Принимает решения на основе экономических показателей."""

    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        # Эвристическая логика на основе безработицы и бюджетного баланса
        current_unempl = context_df["unemployment_rate"].iloc[-1]

        if step == 1:
            mech_type = "income_tax"
            rate = 0.15  # Собираем налоги
        elif current_unempl > 0.05:
            mech_type = "tax_subsidy"
            rate = 0.20  # Агрессивные субсидии
        else:
            mech_type = "tax_subsidy"
            rate = 0.10  # Умеренные субсидии
```

### 📝 LLM Drafter (drafter.py)

Основной компонент генерации политик через LLM:

#### MockLLM

Тестовая реализация LLM без внешних зависимостей:

```python
class MockLLM:
    def invoke(self, prompt: str) -> str:
        """Эмулирует ответ GPT-4, возвращая валидный JSON."""
        return """{"schema_version": "2.0", "semantic": {...}}"""
```

#### drafter_node

LangGraph узел для генерации IR из пользовательского запроса:

- **Вход**: `user_request` из ExperimentState
- **Процесс**: LLM вызов → JSON парсинг → Pydantic валидация
- **Self-healing**: Автоматическое исправление ошибок через repair_ir
- **Аудит**: Полное логирование через append_audit

```python
def drafter_node(state: ExperimentState) -> ExperimentState:
    """Узел Drafter: User Request -> Policy IR JSON."""
    # 1. Валидация входа
    # 2. Подготовка промпта
    # 3. LLM вызов
    # 4. Парсинг и валидация
    # 5. Аудит логирование
```

### 🎯 Системные Промпты (prompts.py)

Каталог промптов для LLM с полной интеграцией механизмами:

#### get_system_prompt()

Генерирует системный промпт с актуальной схемой и механизмами:

```python
def get_system_prompt() -> str:
    schema = PolicySurfaceIR.model_json_schema()
    mechanisms = DEFAULT_MECHANISM_REGISTRY.model_dump(mode="json")

    return f"""You are an AI Policy Architect...

AVAILABLE MECHANISMS (foundry):
{json.dumps(mechanisms, indent=2)}

JSON SCHEMA:
{json.dumps(schema, indent=2)}
"""
```

**Ключевые инструкции:**
- Вывод только валидного JSON
- Использование `tax_subsidy` для субсидий, `income_tax` для налогов
- String/decimal значения для чисел
- Selector AST с explicit clauses

### 🔧 Альтернативные Промпты (prompt.py)

Специализированные промпты для разных сценариев:

#### SYSTEM_PROMPT_TEMPLATE

Шаблон для динамических промптов с контекстом данных:

```python
SYSTEM_PROMPT_TEMPLATE = """
You are the **Policy Scientist** — an advanced AI governing a digital economic simulation.

### YOUR GOAL
Optimize the economic metrics provided by the user...

### CONTEXT
Current Simulation Step: {step}
Recent Economic Data:
{data_context}
"""
```

#### get_system_prompt(step, data_context)

Динамическая генерация промпта с актуальной схемой:

```python
def get_system_prompt(step: int, data_context: str) -> str:
    schema = PolicySurfaceIR.model_json_schema()
    return SYSTEM_PROMPT_TEMPLATE.format(
        schema=json.dumps(schema, indent=2),
        step=step,
        data_context=data_context
    )
```

## API Использование

### Создание и использование агентов

```python
from polisyos.scientist.agent.base import BaseAgent, MockAgent

# Использование готового агента
agent = MockAgent()
policy_ir = agent.decide(step=1, context_df=economic_data)

# Создание кастомного агента
class CustomAgent(BaseAgent):
    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        # Ваша логика принятия решений
        return PolicySurfaceIR(...)
```

### Интеграция с workflow

```python
from polisyos.scientist.orchestrator.workflow import build_workflow

# Workflow автоматически использует drafter_node
workflow = build_workflow()
result = workflow.invoke({
    "user_request": "Reduce poverty through targeted subsidies",
    "optimize": True
})
```

## Тестирование

### Mock компоненты

Для тестирования без LLM зависимостей:

```python
from polisyos.scientist.agent.drafter import MockLLM

llm = MockLLM()
response = llm.invoke("Generate a tax policy")
# Возвращает заранее подготовленный JSON
```

### Unit тесты

```bash
# Тестирование agent layer
pytest tests/scientist/test_agent_*.py -v

# С mock LLM (без API ключей)
pytest tests/scientist/integration/test_workflow_smoke.py -v
```

## Расширение

### Добавление нового агента

```python
from polisyos.scientist.agent.base import BaseAgent
from polisyos.ir.surface import PolicySurfaceIR

class LLMAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name

    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        # Интеграция с реальным LLM API
        response = call_openai_api(self.model_name, ...)
        return PolicySurfaceIR.parse_raw(response)
```

### Кастомные промпты

```python
def get_custom_prompt(scenario: str) -> str:
    """Промпт для специфического сценария политики."""
    base_prompt = get_system_prompt()

    if scenario == "fiscal_policy":
        return base_prompt + "\nFOCUS: Fiscal and monetary policy interactions..."
    elif scenario == "social_policy":
        return base_prompt + "\nFOCUS: Social welfare and inequality reduction..."
```

## Связанные компоненты

- **IR Layer**: `PolicySurfaceIR` для структур политик
- **Kernel Layer**: `DEFAULT_MECHANISM_REGISTRY` для доступных механизмов
- **Orchestrator**: `drafter_node` в workflow
- **Fabric**: Данные для context-aware генерации

## Troubleshooting

### Ошибки валидации IR

```
ValidationError: mechanism_type must be one of: tax_subsidy, income_tax
```

**Решение**: Проверить доступные механизмы в `DEFAULT_MECHANISM_REGISTRY`

### MockLLM не работает

```
AttributeError: 'MockLLM' object has no attribute 'invoke'
```

**Решение**: Убедиться, что используется правильный интерфейс LLM

### Промпт слишком длинный

**Решение**: Оптимизировать промпт или использовать более короткую схему с `mode="json"`