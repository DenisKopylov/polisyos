# Scientist Tests

Валидация компонентов scientist layer - протоколов агентов, компилятора политик и ИИ-компонентов.

**Последнее обновление:** Январь 2026 (добавлены тесты reflexion loop и multi-agent workflow)
**Уровень:** Scientist Layer (AI & Compilation)
**Зависимости:** JAX, Core artifacts, IR structures

## Архитектурный контекст

Scientist layer обеспечивает компиляцию политик из IR в executable формы и управляет AI-компонентами. Тесты валидируют policy compilation pipeline и integration с ИИ.

## Структура тестов

```
scientist/
├── test_agent_protocols.py    # Протоколы агентов: PI, Drafter, Formalizer, Critic
├── test_compiler.py           # Компилятор политик из IR
├── test_multi_agent_workflow.py # Multi-agent workflow с critique system и памятью
└── test_reflexion_loop.py     # Reflexion loop, failure cards, recovery mechanisms
```

## Категории тестов

### Agent Protocols (`test_agent_protocols.py`)

**Цель:** Валидация протоколов агентов и их runtime поведения в полном pipeline.

**Ключевые тесты:**
- **Protocol Conformance**: Проверка реализации интерфейсов PI/Drafter/Formalizer/Critic
- **Runtime Behavior**: Тестирование async execution, delegation, task decomposition
- **Pipeline Flow**: Полный workflow от user request до PolicySurfaceIR через агентов
- **Reflexion Loop**: Critique-based refinement с convergence guarantees
- **Backward Compatibility**: Поддержка legacy MockAgent интерфейсов

**Принципы:**
- **Protocol Compliance**: Строгое следование agent protocol definitions
- **Async Execution**: Правильная обработка asyncio coroutines и delegation
- **State Management**: Корректное управление agent state и problem frames
- **Error Handling**: Graceful handling ошибок в agent interactions

### Policy Compiler (`test_compiler.py`)

**Цель:** Валидация компиляции IR политик в исполняемые модели foundry.

**Ключевые тесты:**
- **IR to Foundry Compilation**: Полный roundtrip IR → compilation → execution → state update
- **Surface IR Roundtrip**: PolicySurfaceIR → executable program → GlobalState changes
- **Registry Integration**: Корректное использование mechanism/slot/merge registries
- **Execution Correctness**: Валидация что скомпилированные программы работают правильно

**Принципы:**
- **Compilation Pipeline**: IR → executable foundry programs
- **Registry-driven**: Использование centralized registries для compilation
- **Execution Safety**: Compiled programs безопасны для execution
- **State Consistency**: Correct state transformations через execution

### Multi-Agent Workflow (`test_multi_agent_workflow.py`)

**Цель:** Тестирование полной интеграции multi-agent системы с critique system и памятью агентов.

**Ключевые тесты:**
- **Workflow Integration**: Полный workflow от user request до valid IR через агентов
- **Critique System**: Генерация actionable hints для policy refinement
- **Memory Persistence**: Сохранение состояния и hints между попытками агентов
- **Short-Term Memory**: Управление памятью агентов с сериализацией и reset

**Принципы:**
- **Workflow Orchestration**: build_workflow() создает полный pipeline
- **Critique Integration**: StaticCritic для тестирования critique responses
- **Memory State**: Persistence hints и attempt history
- **Error Recovery**: Graceful handling critique failures

### Reflexion Loop (`test_reflexion_loop.py`)

**Цель:** Валидация системы reflexion с failure cards, recovery mechanisms и escalation logic.

**Ключевые тесты:**
- **Failure Card Schema**: Создание и валидация failure cards с violations и remediation
- **Reflexion Orchestrator**: Decision making для retry/abort/escalation scenarios
- **Recovery Mechanisms**: Конвертация из critic feedback, validation errors, governor feedback
- **State Management**: Управление retry count, failure history, active failures

**Принципы:**
- **Failure Classification**: Recoverable vs fatal failures с severity levels
- **Retry Logic**: Backoff delays, budget exhaustion, max iteration limits
- **Escalation Paths**: Automatic escalation to human для complex failures
- **Audit Trail**: Complete failure history с content hashing

## Запуск тестов

```bash
# Все scientist тесты
pytest tests/scientist/ -v

# Конкретные компоненты
pytest tests/scientist/test_agent_protocols.py -v
pytest tests/scientist/test_compiler.py -v
pytest tests/scientist/test_multi_agent_workflow.py -v
pytest tests/scientist/test_reflexion_loop.py -v

# Agent pipeline testing
pytest tests/scientist/test_agent_protocols.py::TestAgentPipeline -v

# Multi-agent workflow
pytest tests/scientist/test_multi_agent_workflow.py::TestMultiAgentWorkflow -v
pytest tests/scientist/test_multi_agent_workflow.py::TestShortTermMemory -v

# Reflexion loop и failure cards
pytest tests/scientist/test_reflexion_loop.py::TestReflexionOrchestrator -v
pytest tests/scientist/test_reflexion_loop.py::TestFailureCardSchema -v
pytest tests/scientist/test_reflexion_loop.py::TestFailureCardConverters -v
```

## Связи с другими модулями

### Зависимости Scientist Layer

**IR Layer** (`ir/`):
- **Policy Surface**: Surface IR как input для compilation
- **Semantic Models**: Policy semantics для compilation

**Foundry Layer** (`foundry/`):
- **Execution Engine**: Running скомпилированных программ
- **State Management**: GlobalState updates через execution

**Core Layer** (`core/`):
- **Registry Bundles**: Centralized registries для compilation
- **Artifact Storage**: Persistence compiled programs

### Потребители Scientist Layer

**Integration Layer** (`integration/`):
- **Full Pipeline**: Draft → IR → Compilation → Simulation
- **Workflow Orchestration**: AI-powered policy workflows
- **Reflexion Loop**: Error recovery и retry mechanisms для end-to-end scenarios
- **Failure Cards**: Error handling integration с governor и validation feedback

### Архитектурные инварианты

- **Закон B**: Компиляторная труба (NL → LLM → IR → Compilation → Runtime)
- **Registry Consistency**: Compilation использует consistent registry bundles
- **Execution Correctness**: Compiled programs preserve policy semantics
- **State Safety**: Safe state transformations через execution
- **Failure Recovery**: Все failures имеют structured remediation paths (retry/escalate/abort)
- **Memory Persistence**: Agent state persists across workflow attempts с hint accumulation
- **Critique Integration**: Critique system provides actionable feedback для всех agents
- **Reflexion Convergence**: Retry loops converge или escalate для human intervention

## Разработка и расширение

### Добавление новых scientist тестов

1. Тестируйте compilation для различных типов политик
2. Проверяйте registry integration и consistency
3. Валидируйте execution correctness compiled programs
4. Тестируйте error handling в compilation pipeline
5. Для reflexion loop: тестируйте failure scenarios, recovery paths, escalation logic
6. Для multi-agent workflow: проверяйте state persistence, critique integration, memory management
7. Для failure cards: валидируйте schema compliance, converter accuracy, severity classification
8. Используйте fixtures для shared state (base_state, recoverable_failure_card, fatal_failure_card)

### Структура scientist теста

```python
def test_policy_compilation_roundtrip(tmp_path):
    # Setup: create policy и registries
    policy = create_test_policy()
    registries = load_default_registries(tmp_path)

    # Execute: compile policy
    artifacts = compile_surface_policy(tmp_path, policy, registries)

    # Verify: execute и check results
    state = execute_compiled_program(artifacts)
    validate_policy_effects(state, expected_changes)

def test_reflexion_recovery(base_state, recoverable_failure_card):
    # Setup: orchestrator и failure
    orchestrator = ReflexionOrchestrator(ReflexionConfig())

    # Execute: evaluate failure
    decision = orchestrator.evaluate_failure(recoverable_failure_card, base_state)

    # Verify: correct recovery decision
    assert decision == ReflexionDecision.RETURN_TO_DRAFTER

def test_multi_agent_workflow_memory():
    # Setup: workflow с memory tracking
    workflow = build_workflow()

    # Execute: run workflow с critique
    result = workflow.invoke({
        "user_request": "Test policy",
        "critic_agent": StaticCritic("NEEDS_REVISION", hint="Fix tax rate")
    })

    # Verify: memory persistence
    memory_data = result.get("short_term_memory", {})
    assert memory_data  # Memory should be populated
```

## Troubleshooting

### Распространенные проблемы

**Compilation failures:**
```bash
# Проверьте registry loading
pytest tests/scientist/test_compiler.py::test_compile_surface_policy_roundtrip_rate -v --tb=long
```

**Agent protocol failures:**
```bash
# Проверьте protocol conformance
pytest tests/scientist/test_agent_protocols.py::TestProtocolConformance -v
# Проверьте pipeline flow
pytest tests/scientist/test_agent_protocols.py::TestAgentPipeline::test_full_pipeline_flow -v
```

**Execution errors:**
```bash
# Проверьте state consistency
pytest tests/scientist/test_compiler.py -v -s
```

**Reflexion orchestrator failures:**
```bash
# Проверьте decision logic
pytest tests/scientist/test_reflexion_loop.py::TestReflexionOrchestrator::test_evaluate_recoverable_routes_to_drafter -v
# Проверьте backoff configuration
pytest tests/scientist/test_reflexion_loop.py::TestReflexionOrchestrator::test_backoff_delay_config -v
```

**Failure card conversion issues:**
```bash
# Проверьте converter accuracy
pytest tests/scientist/test_reflexion_loop.py::TestFailureCardConverters -v
# Проверьте schema compliance
pytest tests/scientist/test_reflexion_loop.py::TestFailureCardSchema::test_create_minimal_card -v
```

**Multi-agent workflow issues:**
```bash
# Проверьте workflow orchestration
pytest tests/scientist/test_multi_agent_workflow.py::TestMultiAgentWorkflow::test_workflow_produces_valid_ir -v
# Проверьте memory serialization
pytest tests/scientist/test_multi_agent_workflow.py::TestShortTermMemory::test_serialization_roundtrip -v
```

## Технологии и зависимости

### Core Dependencies
- **JAX**: Execution compiled programs
- **Core Artifacts**: Registry bundles и artifact storage
- **IR Structures**: Policy surface для compilation

### Compilation Infrastructure
- **Policy Compiler**: IR → executable transformation
- **Registry Integration**: Centralized configuration management
- **Execution Engine**: Safe program execution
- **State Management**: GlobalState transformation pipeline

### Reflexion System
- **Failure Card System**: Structured error representation с violations и remediation
- **Reflexion Orchestrator**: Decision engine для retry/abort/escalation logic
- **Recovery Mechanisms**: Converters для critic/validation/governor feedback
- **Backoff Configuration**: Exponential backoff с configurable delays

### Multi-Agent Components
- **Short-Term Memory**: Agent state persistence с hint accumulation
- **Critique System**: Feedback generation для policy refinement
- **Workflow Orchestration**: Multi-agent pipeline coordination
- **State Serialization**: Deterministic state persistence между attempts