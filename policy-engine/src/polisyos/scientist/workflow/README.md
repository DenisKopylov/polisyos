# Workflow Engines: Движки рабочих процессов

**Абстракции и реализации движков для декларативного управления экспериментами с экономическими политиками**

## Обзор

Модуль `workflow` предоставляет унифицированный интерфейс для различных реализаций движков рабочих процессов. Он абстрагирует сложность управления состоянием экспериментов, позволяя использовать как простые последовательные движки, так и сложные графовые workflow с conditional routing.

## Архитектура

### 🏗️ Базовые абстракции

Модуль построен на принципах dependency inversion и protocol-based design:

- **`WorkflowEngine`**: Протокол для унифицированного интерфейса движков
- **`WorkflowEngineFactory`**: Фабрика для создания экземпляров движков
- **Pluggable Architecture**: Возможность замены реализаций без изменения кода клиентов

### ⚙️ Реализации движков

#### SimpleLoopEngine (Простой loop-based движок)
- **Назначение**: Легковесный движок для простых последовательных процессов
- **Использование**: Unit testing, быстрая итерация, surrogate evaluations
- **Особенности**: Минимальный overhead, последовательное выполнение узлов

#### LangGraphEngine (Продвинутый графовый движок)
- **Назначение**: Комплексные workflow с conditional routing и state management
- **Использование**: Полноценные эксперименты с ветвлением и циклами
- **Особенности**: Декларативное определение, observability, error handling

## Структура модуля

```
workflow/
├── __init__.py              # Экспорт основных компонентов
├── engine_base.py           # Базовые абстракции (WorkflowEngine, WorkflowEngineFactory)
├── engine_simple.py         # SimpleLoopEngine для последовательных процессов
└── engine_langgraph.py      # LangGraphEngine для комплексных workflow
```

## Основные компоненты

### 🎯 WorkflowEngine Protocol

Унифицированный интерфейс для всех реализаций движков:

```python
from polisyos.scientist.workflow import WorkflowEngine

class WorkflowEngine(Protocol):
    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить workflow до завершения"""

    def step(self, state: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """Выполнить один шаг workflow"""

    @property
    def current_phase(self) -> str:
        """Текущая фаза FSM (INTAKE, FRAME, EXECUTE, etc.)"""

    @property
    def current_node(self) -> str | None:
        """Имя текущего исполняемого узла"""

    def reset(self) -> None:
        """Сбросить движок в начальное состояние"""
```

**Ключевые преимущества:**
- **Testability**: Легкая замена на mock реализации для тестирования
- **Flexibility**: Возможность миграции между реализациями (LangGraph → Temporal → Prefect)
- **Consistency**: Единый интерфейс для всех типов workflow

### 🏭 WorkflowEngineFactory

Фабрика для создания экземпляров движков:

```python
from polisyos.scientist.workflow import WorkflowEngineFactory, LangGraphEngineFactory

# Создание фабрики
factory = LangGraphEngineFactory()

# Создание экземпляра движка
engine = factory.create(config={"optimization": True})
```

### 🔄 SimpleLoopEngine

Легковесный движок для простых последовательных процессов:

```python
from polisyos.scientist.workflow import SimpleLoopEngine

def draft_node(state):
    # Логика узла draft_ir
    return {**state, "ir": generated_ir}

def validate_node(state):
    # Логика узла validate_ir
    return {**state, "validation_passed": True}

# Создание движка
engine = SimpleLoopEngine([
    ("draft_ir", draft_node),
    ("validate_ir", validate_node),
    ("compile_model", compile_node),
    ("run_sim", simulation_node),
    ("pack_decision", pack_node)
])

# Выполнение
result = engine.run(initial_state)

# Или пошаговое выполнение
state = initial_state
while True:
    state, is_done = engine.step(state)
    if is_done:
        break
```

**Особенности:**
- **Zero Dependencies**: Не требует LangGraph или других внешних библиотек
- **Sequential Execution**: Простое последовательное выполнение узлов
- **Early Termination**: Поддержка преждевременного завершения (pruned workflows)
- **State Tracking**: Отслеживание текущей фазы и узла

**Использование:**
- **Unit Testing**: Тестирование логики workflow без графовых зависимостей
- **Development**: Быстрая итерация во время разработки
- **Cheap Stage**: Surrogate evaluations в search framework
- **Debugging**: Пошаговое выполнение для отладки

### 🌐 LangGraphEngine

Продвинутый движок на базе LangGraph для комплексных workflow:

```python
from polisyos.scientist.workflow import LangGraphEngine, LangGraphEngineFactory

# Создание через фабрику
factory = LangGraphEngineFactory()
engine = factory.create()

# Или напрямую из скомпилированного графа
from polisyos.scientist.orchestrator.workflow import build_workflow
compiled_graph = build_workflow()
engine = LangGraphEngine(compiled_graph)

# Выполнение до завершения
final_state = engine.run(initial_state)

# Получение информации о состоянии
print(f"Current phase: {engine.current_phase}")
print(f"Current node: {engine.current_node}")

# Пошаговое выполнение (эмуляция через streaming)
state, is_terminal = engine.step(current_state)
```

**Особенности:**
- **Graph-Based**: Декларативное определение workflow как графов
- **Conditional Routing**: Ветвление на основе состояния и условий
- **State Management**: Автоматическое управление сложным состоянием
- **Observability**: Встроенная трассировка и мониторинг
- **Error Recovery**: Self-healing циклы и обработка ошибок

## Рабочий процесс

### 1. Выбор подходящего движка

```python
from polisyos.scientist.workflow import SimpleLoopEngine, LangGraphEngineFactory

# Для простых тестов или быстрой итерации
if testing or development:
    engine = SimpleLoopEngine([...])  # Легковесный движок

# Для полноценных экспериментов
else:
    factory = LangGraphEngineFactory()
    engine = factory.create()  # Полноценный графовый движок
```

### 2. Подготовка начального состояния

```python
initial_state = {
    "user_request": "Reduce poverty through targeted subsidies",
    "run_id": "exp_001",
    "budget": {"max_llm_calls": 3, "max_sim_runs": 2},
    "optimize": True,
    "random_seed": 42,
    # ... другие поля ExperimentState
}
```

### 3. Выполнение workflow

```python
# Полное выполнение
final_state = engine.run(initial_state)

# Проверка результатов
decision_packet = final_state.get("decision_packet")
if decision_packet:
    print(f"Policy approved: {decision_packet.feedback.verdict}")
    print(f"Simulation results: {decision_packet.simulation_results}")
```

### 4. Пошаговое выполнение (для отладки)

```python
state = initial_state
step_count = 0

while step_count < max_steps:
    print(f"Step {step_count}: Phase={engine.current_phase}, Node={engine.current_node}")

    new_state, is_terminal = engine.step(state)
    state = new_state
    step_count += 1

    if is_terminal:
        print("Workflow completed")
        break
```

## Интеграция с другими модулями

### 🔗 Связь с Scientist Orchestrator

Workflow engines являются сердцем orchestrator layer:

```python
# В orchestrator/workflow.py используется LangGraphEngine
from polisyos.scientist.workflow import LangGraphEngine

def build_workflow() -> CompiledGraph:
    # Создание и конфигурация LangGraph workflow
    # Возвращает скомпилированный граф для LangGraphEngine
    pass
```

### 🔗 Связь с Search Framework

SimpleLoopEngine используется в search для быстрой оценки:

```python
# В search/stages.py для CheapStage
from polisyos.scientist.workflow import SimpleLoopEngine

class CheapStage:
    def __init__(self, proxy_nodes, terminal_node="pack_decision"):
        self.engine = SimpleLoopEngine(proxy_nodes, terminal_node)

    def evaluate(self, candidate):
        # Быстрая оценка через простой workflow
        result = self.engine.run({"policy_params": candidate})
        return result["objective_value"]
```

### 🔗 Связь с Kernel FSM

Движки интегрируются с kernel для управления фазами:

```python
# Синхронизация фаз между движком и FSM
current_phase = engine.current_phase
kernel_state = kernel_state.with_phase(Phase(current_phase))
```

### 🔗 Связь с Governance

Workflow engines учитывают governance decisions:

```python
# В flow_nodes.py
def governor_node(state):
    # Вызов governance pipeline
    feedback = governance.governor(state)

    if feedback.verdict == "REJECT":
        # LangGraphEngine обработает routing автоматически
        return {**state, "feedback": feedback, "pruned": True}

    return {**state, "feedback": feedback}
```

## Ключевые возможности

### 🔄 Protocol-Based Design

- **Dependency Inversion**: Клиентский код зависит от абстракций, не реализаций
- **Pluggable Engines**: Легкая замена реализаций движков
- **Future-Proof**: Возможность миграции на новые технологии (Temporal, Prefect, Airflow)

### ⚡ Performance Optimization

- **SimpleLoopEngine**: Минимальный overhead для простых сценариев
- **LangGraph Streaming**: Инкрементальное выполнение для больших workflow
- **State Caching**: Переиспользование состояния между шагами

### 🐛 Testing и Debugging

- **Mock Engines**: Простая замена на тестовые реализации
- **Step-by-Step Execution**: Пошаговое выполнение для отладки
- **State Inspection**: Доступ к текущему состоянию и фазе

### 📊 Observability

- **Phase Tracking**: Отслеживание текущей фазы FSM
- **Node Monitoring**: Видимость текущего исполняемого узла
- **State History**: Возможность логирования изменений состояния

## Примеры использования

### Тестирование с SimpleLoopEngine

```python
from polisyos.scientist.workflow import SimpleLoopEngine

def mock_draft_ir(state):
    return {**state, "ir": {"mock": True}}

def mock_validate_ir(state):
    return {**state, "validation_passed": True}

def mock_pack_decision(state):
    return {**state, "decision_packet": {"mock_result": True}}

# Создание тестового движка
test_engine = SimpleLoopEngine([
    ("draft_ir", mock_draft_ir),
    ("validate_ir", mock_validate_ir),
    ("pack_decision", mock_pack_decision)
])

# Запуск теста
result = test_engine.run({"user_request": "test"})
assert result["decision_packet"]["mock_result"] == True
```

### Использование в Search Framework

```python
from polisyos.scientist.workflow import SimpleLoopEngine
from polisyos.scientist.search import CheapStage

# Узлы для быстрой оценки
cheap_nodes = [
    ("evaluate_objective", lambda s: {**s, "score": fast_evaluate(s["candidate"])}),
]

# Создание cheap stage с workflow движком
cheap_stage = CheapStage(
    engine=SimpleLoopEngine(cheap_nodes),
    max_evaluations=10
)

# Использование в поиске
result = await cheap_stage.evaluate(policy_candidate)
```

### Продвинутый workflow с LangGraph

```python
from polisyos.scientist.workflow import LangGraphEngineFactory
from polisyos.scientist.orchestrator.workflow import build_workflow

# Создание полноценного workflow
factory = LangGraphEngineFactory()
engine = factory.create()

# Конфигурация эксперимента
experiment_config = {
    "user_request": "Design UBI policy with fiscal constraints",
    "budget": {"max_llm_calls": 5, "max_sim_runs": 3},
    "governance_profile": "strict",
    "optimization_enabled": True
}

# Выполнение эксперимента
result = engine.run(experiment_config)

# Анализ результатов
decision_card = result.get("decision_card")
if decision_card:
    print(f"Policy: {decision_card.title}")
    print(f"Verdict: {decision_card.verdict}")
    print(f"Key metrics: {decision_card.key_metrics}")
```

### Кастомный движок

```python
from polisyos.scientist.workflow import WorkflowEngine, WorkflowEngineFactory

class CustomWorkflowEngine:
    """Кастомная реализация для специфических нужд"""

    def __init__(self, custom_config):
        self.config = custom_config
        self._phase = "INTAKE"
        self._node = None

    def run(self, initial_state):
        # Кастомная логика выполнения
        state = initial_state
        for step in self.config["steps"]:
            state = self._execute_step(step, state)
        return state

    def step(self, state):
        # Пошаговое выполнение
        # ... реализация
        pass

    @property
    def current_phase(self):
        return self._phase

    @property
    def current_node(self):
        return self._node

    def reset(self):
        self._phase = "INTAKE"
        self._node = None

# Реализация фабрики
class CustomEngineFactory:
    def create(self, config=None):
        return CustomWorkflowEngine(config or {})
```

## Тестирование

### Структура тестов

```
tests/scientist/workflow/
├── test_engine_base.py     # Тестирование протоколов
├── test_simple_engine.py   # Тестирование SimpleLoopEngine
├── test_langgraph_engine.py # Тестирование LangGraphEngine
└── integration/
    ├── test_workflow_execution.py  # Интеграционные тесты
    └── test_engine_switching.py    # Тестирование замены движков
```

### Запуск тестов

```bash
# Тестирование абстракций
pytest tests/scientist/workflow/test_engine_base.py -v

# Тестирование реализаций
pytest tests/scientist/workflow/test_simple_engine.py -v
pytest tests/scientist/workflow/test_langgraph_engine.py -v

# Интеграционные тесты
pytest tests/scientist/workflow/integration/ -v
```

### Mock testing

```python
from polisyos.scientist.workflow import WorkflowEngine
from unittest.mock import Mock

# Создание mock движка
mock_engine = Mock(spec=WorkflowEngine)
mock_engine.run.return_value = {"result": "success"}
mock_engine.current_phase = "DECIDE"
mock_engine.current_node = "pack_decision"

# Использование в тестах
result = mock_engine.run(initial_state)
assert result["result"] == "success"
```

## Производительность

### Метрики производительности

- **SimpleLoopEngine**: ~10-100μs на узел, минимальный overhead
- **LangGraphEngine**: ~1-10ms на узел, зависит от сложности графа
- **Memory Usage**: ~1-5MB для типичного эксперимента
- **Scalability**: Поддержка сотен узлов в комплексных workflow

### Оптимизации

- **Lazy Loading**: Импорт тяжелых зависимостей (LangGraph) только при необходимости
- **State Diffing**: Передача только измененных частей состояния
- **Caching**: Переиспользование скомпилированных графов

## Будущие улучшения

### 🚀 Планируемые возможности

- **Temporal.io Integration**: Распределенное выполнение workflow
- **Prefect Integration**: Dataflow-based orchestration
- **Kubernetes Operator**: Нативная поддержка K8s
- **Workflow Templates**: Переиспользуемые паттерны workflow

### 🔬 Продвинутые возможности

- **Distributed Execution**: Workflow на кластере
- **Event-Driven Workflow**: Реактивное выполнение на событиях
- **Workflow Versioning**: Управление версиями определений workflow
- **Visual Workflow Designer**: GUI для создания workflow

### 📊 Observability и Monitoring

- **Workflow Metrics**: Детальная телеметрия выполнения
- **Performance Profiling**: Анализ узких мест в workflow
- **Distributed Tracing**: Отслеживание выполнения в распределенных системах
- **Real-time Dashboard**: Мониторинг активных workflow