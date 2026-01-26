# Agent Layer: Иерархическая система AI агентов

**Протокольная архитектура для генерации и валидации экономических политик**

Agent Layer реализует иерархическую систему специализированных AI агентов (PI → Drafter → Formalizer → Critic) для структурированного решения задач policy design через декомпозицию, генерацию, формализацию и валидацию.

## Обзор

Папка `agent/` реализует иерархическую систему AI агентов для решения комплексных задач policy design. Архитектура следует паттерну Hierarchical Agent Orchestration с четким разделением ответственности между ролями и протоколами коммуникации.

## Архитектура

```
agent/
├── __init__.py           # Экспорт протоколов, ролей и mock реализаций
├── protocols.py          # Протоколы агентов и поддерживающие типы данных
├── pi.py                 # Principal Investigator (PI) Agent
├── drafter.py            # Drafter Agent для генерации черновиков
├── formalizer.py         # Formalizer Agent для преобразования в IR
├── critic.py             # Critic Agent для валидации и критики
└── base.py               # Legacy поддержка (BaseAgent, MockAgent)
```

### Иерархическая архитектура

```
User Request
    ↓
🧠 PI Agent (Principal Investigator)
    - Декомпозиция задачи на подзадачи
    - Определение зависимостей
    - Назначение ролей агентам
    ↓
📝 Drafter Agent
    - Генерация естественных черновиков политик
    - Контекстуализация требований
    - Нарративное описание решений
    ↓
🔧 Formalizer Agent
    - Преобразование черновиков в PolicySurfaceIR
    - Схема валидация и типизация
    - Структурирование параметров
    ↓
⚖️ Critic Agent
    - Многоуровневая валидация
    - Проверка alignment, completeness, consistency
    - Оценка feasibility и compliance
    ↓
Decision Packet
```

## Компоненты

### 📋 Протоколы и типы данных (protocols.py)

#### Роли агентов (AgentRole)
```python
class AgentRole(str, Enum):
    PI = "pi"              # Principal Investigator - декомпозиция задач
    DRAFTER = "drafter"    # Drafter - генерация черновиков
    FORMALIZER = "formalizer"  # Formalizer - формализация в IR
    CRITIC = "critic"      # Critic - валидация и критика
```

#### Ключевые артефакты

**ProblemFrame**: Формализованное описание проблемы (immutable)
```python
@dataclass(frozen=True, slots=True)
class ProblemFrame:
    frame_id: str
    domain: str                    # Домен политики (fiscal, social, etc.)
    problem_statement: str         # Описание проблемы
    actors: tuple[str, ...]        # Затронутые стороны
    goals: tuple[str, ...]         # Цели политики
    constraints: tuple[str, ...]   # Ограничения
    success_criteria: dict         # Критерии успеха
```

**SubTask**: Структура для декомпозиции задач
```python
@dataclass(frozen=True, slots=True)
class SubTask:
    task_id: str
    description: str
    target_agent: AgentRole
    priority: TaskPriority
    status: TaskStatus
    dependencies: tuple[str, ...]
```

**CritiqueReport**: Структурированные отчеты о валидации
```python
@dataclass
class CritiqueReport:
    report_id: str
    verdict: str                    # "APPROVE", "REJECT", "NEEDS_REVISION"
    issues: list[CritiqueIssue]     # Детали проблем
    confidence: float              # Уверенность в оценке
```

### 🧠 Principal Investigator (PI) Agent (pi.py)

**Роль**: Декомпозиция высокоуровневых задач на управляемые подзадачи

**Основные функции**:
- Анализ пользовательского запроса
- Определение домена и контекста проблемы
- Создание ProblemFrame артефакта
- Декомпозиция на SubTask'и с зависимостями
- Назначение подходящих агентов для каждой подзадачи

```python
class MockPIAgent:
    async def decompose_task(
        self, request: str, *, context: dict | None = None
    ) -> list[SubTask]:
        # Анализ запроса и создание подзадач
        # Возврат списка SubTask с target_agent, priority, dependencies
```

### 📝 Drafter Agent (drafter.py)

**Роль**: Генерация естественных черновиков политик из формализованных требований

**Основные функции**:
- Получение ProblemFrame от PI Agent
- Генерация narrativa решений
- Контекстуализация экономических trade-offs
- Создание DraftResult артефакта

```python
class MockDrafterAgent:
    async def draft(
        self, problem_frame: ProblemFrame, *, context: dict | None = None
    ) -> DraftResult:
        # Генерация естественного описания политики
        # Возврат DraftResult с narrative и metadata
```

### 🔧 Formalizer Agent (formalizer.py)

**Роль**: Преобразование естественных черновиков в формальный PolicySurfaceIR

**Основные функции**:
- Парсинг DraftResult от Drafter
- Маппинг на механизмы политики из DEFAULT_MECHANISM_REGISTRY
- Создание валидной структуры IR
- Схема валидация и типизация параметров

```python
class MockFormalizerAgent:
    async def formalize(
        self, draft: DraftResult, *, schema_version: str = "2.0"
    ) -> "PolicySurfaceIR":
        # Преобразование draft в структурированный IR
        # Возврат валидного PolicySurfaceIR объекта
```

### ⚖️ Critic Agent (critic.py)

**Роль**: Комплексная валидация и критика сгенерированных политик

**Основные функции**:
- Проверка alignment с ProblemFrame
- Оценка completeness и consistency
- Анализ feasibility и потенциального воздействия
- Проверка compliance с правилами и регуляциями
- Генерация структурированного CritiqueReport

```python
class MockCriticAgent:
    async def critique(
        self, ir: "PolicySurfaceIR", problem_frame: ProblemFrame, *, depth: str = "standard"
    ) -> CritiqueReport:
        # Комплексная валидация политики
        # Возврат CritiqueReport с verdict и issues
```

### 🔄 Legacy поддержка (base.py)

**BaseAgent и MockAgent** - устаревшие компоненты для обратной совместимости:

```python
class BaseAgent(ABC):
    @abstractmethod
    def decide(self, step: int, context_df) -> PolicySurfaceIR:
        """Legacy интерфейс для простых агентов."""
        pass

class MockAgent(BaseAgent):
    """Простой эвристический агент для базовых сценариев."""
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

### Работа с иерархической системой агентов

```python
from polisyos.scientist.agent import (
    MockPIAgent, MockDrafterAgent, MockFormalizerAgent, MockCriticAgent,
    ProblemFrame, AgentRole, TaskPriority
)

# Создание агентов
pi_agent = MockPIAgent()
drafter_agent = MockDrafterAgent()
formalizer_agent = MockFormalizerAgent()
critic_agent = MockCriticAgent()

# 1. PI Agent декомпозирует задачу
subtasks = await pi_agent.decompose_task(
    "Implement progressive taxation to reduce inequality",
    context={"domain": "fiscal_policy"}
)

# 2. Drafter Agent создает черновик
draft_result = await drafter_agent.draft(
    problem_frame=subtasks[0],  # Из PI декомпозиции
    context={"economic_context": "high_inequality"}
)

# 3. Formalizer Agent преобразует в IR
policy_ir = await formalizer_agent.formalize(
    draft=draft_result,
    schema_version="2.0"
)

# 4. Critic Agent валидирует результат
critique_report = await critic_agent.critique(
    ir=policy_ir,
    problem_frame=subtasks[0],
    depth="standard"
)

# Анализ результатов
if critique_report.verdict == "APPROVE":
    print("✅ Policy approved by Critic Agent")
else:
    print(f"❌ Issues found: {len(critique_report.issues)}")
    for issue in critique_report.issues:
        print(f"  - {issue.category}: {issue.message}")
```

### Интеграция с workflow

```python
from polisyos.scientist.orchestrator.workflow import build_workflow

# Workflow автоматически использует иерархическую систему агентов
workflow = build_workflow()
result = workflow.invoke({
    "user_request": "Reduce poverty through targeted subsidies",
    "optimize": True
})

# Результат включает critique report и decision packet
decision_packet = result.get("decision_packet")
if decision_packet and decision_packet.feedback:
    print(f"Governor verdict: {decision_packet.feedback.verdict}")
```

## Тестирование

### Mock реализации для всех ролей

Для тестирования без внешних зависимостей:

```python
from polisyos.scientist.agent import (
    MockPIAgent, MockDrafterAgent, MockFormalizerAgent, MockCriticAgent
)

# Все mock агенты работают детерминированно
pi_agent = MockPIAgent()
drafter_agent = MockDrafterAgent()
formalizer_agent = MockFormalizerAgent()
critic_agent = MockCriticAgent()

# Тестирование полного цикла
subtasks = await pi_agent.decompose_task("Test policy")
draft = await drafter_agent.draft(subtasks[0])
ir = await formalizer_agent.formalize(draft)
critique = await critic_agent.critique(ir, subtasks[0])
```

### Unit тесты

```bash
# Тестирование всех агентов
pytest tests/scientist/test_agent_*.py -v

# Конкретные роли
pytest tests/scientist/test_agent_pi.py -v        # PI Agent
pytest tests/scientist/test_agent_drafter.py -v   # Drafter Agent
pytest tests/scientist/test_agent_formalizer.py -v # Formalizer Agent
pytest tests/scientist/test_agent_critic.py -v    # Critic Agent

# Integration testing
pytest tests/scientist/integration/test_agent_hierarchy.py -v
pytest tests/scientist/integration/test_workflow_smoke.py -v
```

### Test Coverage

- **Протоколы**: Валидация интерфейсов и типов данных
- **PI Agent**: Декомпозиция задач, создание ProblemFrame
- **Drafter Agent**: Генерация черновиков, контекстуализация
- **Formalizer Agent**: IR генерация, схема валидация
- **Critic Agent**: Многоуровневая валидация, critique reports
- **Integration**: Полный цикл агентов, error handling

## Расширение

### Создание кастомного агента

#### Кастомный Drafter Agent с LLM интеграцией

```python
from polisyos.scientist.agent.protocols import DrafterAgent, ProblemFrame, DraftResult
import openai

class LLMDrafterAgent(DrafterAgent):
    def __init__(self, model_name: str = "gpt-4"):
        self.model_name = model_name
        self.client = openai.OpenAI()

    async def draft(self, problem_frame: ProblemFrame, *, context=None) -> DraftResult:
        prompt = self._build_draft_prompt(problem_frame)

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return DraftResult(
            draft_id=f"llm_draft_{problem_frame.frame_id}",
            narrative=response.choices[0].message.content,
            metadata={"model": self.model_name, "temperature": 0.7}
        )

    def _build_draft_prompt(self, problem_frame: ProblemFrame) -> str:
        return f"""
        You are a Policy Drafter. Create a natural language description of a policy that addresses:

        Problem: {problem_frame.problem_statement}
        Domain: {problem_frame.domain}
        Goals: {', '.join(problem_frame.goals)}
        Constraints: {', '.join(problem_frame.constraints)}

        Provide a comprehensive policy draft that considers economic trade-offs and implementation feasibility.
        """
```

#### Кастомный Critic Agent с доменными правилами

```python
from polisyos.scientist.agent.protocols import CriticAgent, CritiqueReport, CritiqueIssue, CritiqueCategory

class DomainSpecificCriticAgent(CriticAgent):
    def __init__(self, domain_rules: dict):
        self.domain_rules = domain_rules

    async def critique(self, ir, problem_frame, *, depth="standard"):
        issues = []

        # Доменная валидация
        domain_issues = self._check_domain_rules(ir, problem_frame.domain)
        issues.extend(domain_issues)

        # Стандартная валидация
        standard_issues = self._check_standard_validation(ir)
        issues.extend(standard_issues)

        # Определение verdict
        has_blockers = any(i.severity == "blocker" for i in issues)
        verdict = "REJECT" if has_blockers else "APPROVE"

        return CritiqueReport(
            report_id=f"domain_critique_{ir.schema_version}",
            verdict=verdict,
            issues=issues,
            confidence=0.9
        )
```

### Добавление новой роли агента

```python
from polisyos.scientist.agent.protocols import AgentRole

# Расширение enum'а ролей (в отдельном модуле)
class ExtendedAgentRole(str, Enum):
    SPECIALIST = "specialist"      # Доменный специалист
    REVIEWER = "reviewer"         # Рецензент
    OPTIMIZER = "optimizer"       # Оптимизатор параметров

# Создание протокола для новой роли
from typing import Protocol

class SpecialistAgent(Protocol):
    async def specialize(
        self, problem_frame: ProblemFrame, domain_focus: str, *, context=None
    ) -> SpecializedAnalysis:
        """Доменная специализация для конкретной области."""
        ...
```

## Связанные компоненты

- **IR Layer**: `PolicySurfaceIR` для формальных структур политик
- **Kernel Layer**: FSM phases, guards, human gates для контроля выполнения
- **Orchestrator**: Workflow orchestration, state management, decision packets
- **Fabric Layer**: Data access для context-aware генерации
- **Foundry**: Mechanism registry и compilation для policy execution

## Troubleshooting

### Ошибки декомпозиции задач (PI Agent)

```
ValueError: Request cannot be empty
```

**Решение**: Убедиться, что пользовательский запрос не пустой и содержит достаточно контекста для декомпозиции

### Ошибки формализации (Formalizer Agent)

```
ValidationError: Invalid mechanism type in interventions
```

**Решение**: Проверить доступные механизмы в `DEFAULT_MECHANISM_REGISTRY` и соответствие черновика структуре IR

### Critic Agent возвращает неожиданный verdict

```
Unexpected verdict: REJECT with no issues
```

**Решение**: Проверить логику валидации Critic Agent - возможно, проблема с severity classification или confidence thresholds

### Проблемы с async/await

```
TypeError: object NoneType can't be used in 'await' expression
```

**Решение**: Убедиться, что все агенты реализуют async методы согласно протоколам

### Protocol validation errors

```
TypeError: X does not implement protocol Y
```

**Решение**: Проверить, что кастомный агент правильно реализует все required методы протокола

### Промпт слишком длинный

**Решение**: Оптимизировать промпт или использовать более короткую схему с `mode="json"`