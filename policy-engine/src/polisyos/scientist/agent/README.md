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
├── failure_card.py       # Структурированные артефакты для self-healing
├── memory.py             # Кратковременная память для Reflexion
├── reflexion.py          # Оркестратор self-healing workflow
├── prompts.py            # Системные промпты для LLM
├── prompt.py             # Альтернативные промпты (legacy)
└── base.py               # Legacy поддержка (BaseAgent, MockAgent)
```

### Self-Healing система (Reflexion Pattern)

Agent Layer реализует паттерн Reflexion для автономного исправления ошибок и self-healing workflows:

#### FailureCard (failure_card.py)

Структурированный артефакт для фиксации и обработки ошибок:

```python
class FailureCard(BaseModel):
    """Структурированный failure artifact для Reflexion loop."""

    # Идентификация
    card_id: UUID
    source_step: FailureSource  # CRITIC, GOVERNOR_SAFETY, etc.
    run_id: str

    # Классификация ошибки
    error_code: str
    severity: FailureSeverity  # RECOVERABLE, NEEDS_HUMAN, FATAL
    violation_summary: str

    # Технические детали
    violations: List[ConstraintViolation]
    technical_details: Dict[str, Any]
    state_diff: Optional[StateDiff]

    # Руководство по исправлению
    remediation_advice: str
    governor_advice: Optional[str]
    remediation_target: RemediationTarget  # FORMALIZER, DRAFTER, HUMAN, NONE

    # Управление итерациями
    attempt_number: int
    max_iterations: int

    # Ссылки на артефакты
    failed_artifact_ref: Optional[str]
    previous_card_ref: Optional[str]
```

**Ключевые возможности:**
- Автоматическая классификация severity и remediation target
- Content-addressable hashing для reproducible tracking
- Форматирование для LLM context injection
- Конвертеры из Critic feedback, validation errors, governor feedback

#### ShortTermMemory (memory.py)

Кратковременная память для отслеживания conversation и попыток в рамках одного эксперимента:

```python
class ShortTermMemory:
    """Short-term memory for a single experiment run."""

    def add_turn(self, role: TurnRole, content: str, **metadata) -> None:
        """Добавить turn в conversation память."""

    def add_attempt(self, draft_summary: str, ir_summary: str,
                   critique_verdict: str, critique_hint: str) -> None:
        """Записать попытку формализации для Reflexion."""

    def get_hints(self) -> List[str]:
        """Получить все накопленные hints от Critic reviews."""
```

**Роли в памяти:**
- USER, PI, DRAFTER, FORMALIZER, CRITIC, SYSTEM

#### ReflexionOrchestrator (reflexion.py)

Оркестратор self-healing workflow с intelligent routing и backoff:

```python
class ReflexionOrchestrator:
    """Координатор Reflexion loop для self-healing workflows."""

    def evaluate_failure(self, card: FailureCard, state: ExperimentState) -> ReflexionDecision:
        """Оценить failure и принять решение о next action."""

    def prepare_retry_context(self, card: FailureCard, state: ExperimentState) -> Dict[str, Any]:
        """Подготовить context для retry attempt."""

    async def apply_backoff(self, attempt: int) -> None:
        """Применить exponential backoff delay."""
```

**Решения Reflexion:**
- RETURN_TO_FORMALIZER: Технические проблемы (schema, compilation)
- RETURN_TO_DRAFTER: Концептуальные проблемы (alignment, scope)
- ESCALATE_TO_HUMAN: Требуется человеческое решение
- ABORT_WITH_REPORT: Фатальные ошибки или исчерпан бюджет

**Self-Healing Workflow:**
```
Detect Failure → Evaluate → Route → Inject Context → Retry
      ↓              ↓         ↓         ↓              ↓
FailureCard → Decision → Target → Prompt Context → Attempt
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

### Работа с Self-Healing компонентами

```python
from polisyos.scientist.agent.failure_card import FailureCard, from_critic_feedback, from_validation_error
from polisyos.scientist.agent.memory import ShortTermMemory, TurnRole
from polisyos.scientist.agent.reflexion import ReflexionOrchestrator, ReflexionDecision

# Создание FailureCard из Critic feedback
critique_feedback = {
    "verdict": "NEEDS_REVISION",
    "issues": [{"message": "Invalid mechanism type", "category": "schema"}],
    "summary": "Policy contains invalid mechanisms"
}

failure_card = from_critic_feedback(
    critique=critique_feedback,
    run_id="exp_001",
    attempt_number=1,
    failed_artifact_ref="sha256:abcd1234"
)

# Работа с памятью
memory = ShortTermMemory(max_turns=50, max_attempts=10)

# Добавление conversation turns
memory.add_turn(TurnRole.USER, "Reduce poverty through subsidies")
memory.add_turn(TurnRole.DRAFTER, "Generated policy draft with tax subsidies")
memory.add_turn(TurnRole.CRITIC, "Policy needs revision: invalid subsidy mechanism")

# Добавление попыток
memory.add_attempt(
    draft_summary="Basic subsidy policy",
    ir_summary="Tax subsidy mechanism with 5% rate",
    critique_verdict="NEEDS_REVISION",
    critique_hint="Use 'tax_subsidy' instead of 'subsidy'"
)

# Получение hints для следующей попытки
hints = memory.get_hints()  # ["Use 'tax_subsidy' instead of 'subsidy'"]

# Форматирование истории для LLM
conversation_history = memory.get_history_as_text(last_n=10)

# Reflexion Orchestrator
orchestrator = ReflexionOrchestrator()

# Оценка failure и принятие решения
decision = orchestrator.evaluate_failure(failure_card, experiment_state)

if decision == ReflexionDecision.RETURN_TO_FORMALIZER:
    # Техническая проблема - вернуть Formalizer
    retry_context = orchestrator.prepare_retry_context(failure_card, experiment_state)
    # Inject context into next attempt
elif decision == ReflexionDecision.RETURN_TO_DRAFTER:
    # Концептуальная проблема - вернуть Drafter
    pass
elif decision == ReflexionDecision.ESCALATE_TO_HUMAN:
    # Требуется человеческое вмешательство
    pass

# Применение backoff delay
await orchestrator.apply_backoff(attempt=2)
```

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
- **FailureCard**: Создание, классификация, formatting для LLM
- **ShortTermMemory**: Conversation tracking, attempt recording, hints accumulation
- **ReflexionOrchestrator**: Failure evaluation, routing decisions, backoff logic
- **Integration**: Полный цикл агентов, self-healing workflows, error recovery

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

### Кастомные FailureCard конвертеры

```python
from polisyos.scientist.agent.failure_card import FailureCard, FailureSource, RemediationTarget

def from_custom_error(error_type: str, details: dict, run_id: str) -> FailureCard:
    """Создание FailureCard из кастомной ошибки."""

    # Автоматическая классификация
    if "validation" in error_type:
        source = FailureSource.VALIDATOR_SCHEMA
        target = RemediationTarget.FORMALIZER
    elif "alignment" in error_type:
        source = FailureSource.CRITIC
        target = RemediationTarget.DRAFTER
    else:
        source = FailureSource.UNKNOWN
        target = RemediationTarget.NONE

    return FailureCard.generate(
        source_step=source,
        error_code=error_type.upper(),
        violation_summary=details.get("message", "Custom error occurred"),
        remediation_advice=details.get("fix_suggestion", "Review and fix the error"),
        run_id=run_id,
        remediation_target=target,
        technical_details=details
    )
```

### Расширение ShortTermMemory

```python
class EnhancedShortTermMemory(ShortTermMemory):
    """Расширенная память с дополнительными возможностями."""

    def add_performance_metric(self, metric_name: str, value: float, attempt: int) -> None:
        """Записать метрику производительности для попытки."""
        self._performance_history[attempt] = {metric_name: value}

    def get_performance_trends(self) -> dict:
        """Анализ трендов производительности по попыткам."""
        return self._analyze_performance_trends()

    def suggest_improvements(self) -> List[str]:
        """Предложить улучшения на основе истории."""
        trends = self.get_performance_trends()
        return self._generate_improvement_suggestions(trends)
```

### Кастомный ReflexionOrchestrator

```python
class AdvancedReflexionOrchestrator(ReflexionOrchestrator):
    """Расширенный оркестратор с ML-based routing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._routing_model = self._load_routing_model()  # ML модель для routing

    def evaluate_failure(self, card: FailureCard, state) -> ReflexionDecision:
        # Сначала базовая логика
        base_decision = super().evaluate_failure(card, state)

        # Затем ML-based refinement
        features = self._extract_features(card, state)
        ml_decision = self._routing_model.predict(features)

        # Combine base + ML decisions
        return self._combine_decisions(base_decision, ml_decision)
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