# Search Tests

Валидация search loop system - Phase 17 optimization, two-stage filtering, stopping criteria, objective functions, candidate generation.

**Последнее обновление:** 1 февраля 2026 (Phase 17 optimization, two-stage filtering, search controller, stopping criteria, workflow engines)
**Уровень:** Search Layer (Optimization & Refinement)
**Зависимости:** JAX, Core artifacts, IR structures, Foundry execution, Fabric trust, Workflow engines

## Архитектурный контекст

Search layer реализует Phase 17 optimization - iterative policy refinement через two-stage filtering, stopping criteria и objective functions. SearchController управляет optimization loop, candidate generators создают новые policy variants, а workflow engines обеспечивают execution orchestration.

## Структура тестов

```
search/
├── conftest.py            # Специфичная конфигурация для search тестов
├── test_search_loop.py    # SearchController, two-stage filtering, stopping criteria, objectives
└── strategies/            # Advanced strategy tests (adapter, space, BO/MO fallbacks, batch)
└── __init__.py
```

## Категории тестов

### Search Loop System (`test_search_loop.py`)

**Цель:** Валидация Phase 17 optimization - iterative policy refinement с two-stage filtering, stopping criteria и objective functions.

**Ключевые тесты:**
- **Optimization Flow**: SearchController convergence к optimal policies (quadratic minimization example)
- **Two-Stage Filtering**: Cheap stage rejection prevents expensive evaluation waste, efficiency validation
- **Stopping Criteria**: MaxIterations/MaxWallTime/ImprovementPlateau triggers, composite logic
- **Workflow Engine Abstraction**: Protocol compliance, SimpleLoopEngine step-by-step execution
- **Objectives Evaluation**: GDP growth maximization, composite objectives weighting, normalization
- **Candidate Generation**: History-aware generation, convergence toward optimal solutions
- **Integration Testing**: End-to-end search pipeline validation

**Принципы:**
- **Two-Stage Efficiency**: Cheap filtering (Stage A) prevents expensive simulation (Stage B) calls
- **Convergence Guarantee**: Search loops find optimal policies или escalate appropriately
- **Composite Stopping**: Multiple criteria prevent infinite loops с graceful degradation
- **Engine Abstraction**: WorkflowEngine protocol enables LangGraph/Temporal/Prefect migration
- **Objective Normalization**: Unified minimization convention для multi-objective optimization

## Детальное описание компонентов

### SearchController

**Цель:** Orchestrator для optimization loops с result tracking и status management.

**Ключевые возможности:**
- **Configuration Management**: SearchConfig с stopping criteria, objectives, iteration limits
- **Candidate Generation**: Protocol-based generation через CandidateGenerator interface
- **Two-Stage Execution**: Cheap/expensive evaluation pipeline
- **Result Tracking**: SearchResult с best candidate, iteration history, stopping reason
- **Status Management**: SearchIteration tracking objective values, stage evaluations, timing

**Тестирование:**
```python
def test_search_convergence_to_known_optimum(mock_candidate_generator, quadratic_objective):
    """Тестирование convergence к known optimum (x=0 для f(x)=x^2)."""
    config = SearchConfig(
        stopping=MaxIterations(20),
        objective=quadratic_objective,
    )

    controller = SearchController(
        config=config,
        candidate_generator=mock_candidate_generator,
        stage_a_evaluator=stage_a_evaluator,
        stage_b_evaluator=stage_b_evaluator,
    )

    result = controller.run({"user_request": "Minimize quadratic function"})
    assert abs(result.best_candidate["x"]) < 0.01  # Converged to x=0
```

### Two-Stage Filtering

**Цель:** Cost-effective optimization через cheap/expensive evaluation pipeline.

**Архитектура:**
- **Stage A (Cheap)**: Fast evaluation для rejection invalid candidates
- **Stage B (Expensive)**: Full simulation для valid candidates
- **Efficiency Gains**: Prevents expensive evaluation waste

**Тестирование:**
```python
def test_two_stage_filtering_prevents_expensive_calls(mock_candidate_generator, quadratic_objective):
    """Тестирование что Stage A rejection предотвращает Stage B вызовы."""
    stage_b_call_count = [0]

    def stage_a_evaluator(candidate, context):
        return 1.0, False  # Always reject in cheap stage

    def stage_b_evaluator(candidate, context):
        stage_b_call_count[0] += 1  # Should never be called
        return {"simulation_results": {}, "feedback": {"verdict": "APPROVE"}}

    controller = SearchController(
        config=SearchConfig(stopping=MaxIterations(5), enable_stage_a=True),
        candidate_generator=mock_candidate_generator,
        stage_a_evaluator=stage_a_evaluator,
        stage_b_evaluator=stage_b_evaluator,
    )

    result = controller.run({"user_request": "Test filtering"})
    assert stage_b_call_count[0] == 0  # Stage B never called
    assert result.stage_a_evaluations == 5
    assert result.stage_b_evaluations == 0
```

### Stopping Criteria

**Цель:** Управление optimization termination с composite logic.

**Типы критериев:**
- **MaxIterations**: Ограничение по количеству iterations
- **MaxWallTime**: Ограничение по времени выполнения
- **ImprovementPlateau**: Остановка при отсутствии improvement

**Composite Logic:**
```python
composite = CompositeStoppingCriterion([
    MaxIterations(100),    # Won't trigger
    MaxWallTime(0.01),     # Will trigger after sleep
])

# Stops when ANY criterion triggers
result = composite.check(history, {})
assert result.should_stop
```

### Objective Functions

**Цель:** Evaluation metrics для policy optimization.

**Типы objectives:**
- **GDP Growth Maximization**: Экономический рост как primary objective
- **Composite Objectives**: Weighted combination multiple metrics
- **Normalization**: Unified minimization convention

**Тестирование:**
```python
def test_gdp_objective_maximizes(gdp_objective):
    """Тестирование GDP objective правильно maximizes growth."""
    # Higher GDP should give better (lower) objective value
    high_gdp_result = {"simulation_results": {"gdp_growth": 0.08}}
    low_gdp_result = {"simulation_results": {"gdp_growth": 0.02}}

    high_score = gdp_objective.evaluate(high_gdp_result)
    low_score = gdp_objective.evaluate(low_gdp_result)

    assert high_score < low_score  # Lower score = better for minimization
```

### Workflow Engine Abstraction

**Цель:** Protocol-based execution orchestration.

**Поддерживаемые engines:**
- **SimpleLoopEngine**: Step-by-step execution для testing
- **LangGraph**: Production multi-agent orchestration
- **Temporal/Prefect**: Future workflow backends

**Protocol Compliance:**
```python
def test_workflow_engine_step_execution():
    """Тестирование step-by-step выполнения SimpleLoopEngine."""
    engine = SimpleLoopEngine([
        ("node_a", lambda state: {**state, "phase": "a_completed"}),
        ("node_b", lambda state: {**state, "phase": "b_completed"}),
        ("node_c", lambda state: {**state, "phase": "c_completed"}),
    ])

    state = {"initial": True}
    state, done = engine.step(state)
    assert state["phase"] == "a_completed"
    assert not done

    state, done = engine.step(state)
    assert state["phase"] == "b_completed"
    assert not done

    state, done = engine.step(state)
    assert state["phase"] == "c_completed"
    assert done
```

## Запуск тестов

```bash
# Все search тесты
pytest tests/scientist/search/ -v

# Конкретные компоненты
pytest tests/scientist/search/test_search_loop.py::TestOptimizationFlow -v          # Quadratic convergence
pytest tests/scientist/search/test_search_loop.py::TestTwoStageFiltering -v         # Cheap/expensive stages
pytest tests/scientist/search/test_search_loop.py::TestStoppingCriteria -v          # MaxIterations, Plateau
pytest tests/scientist/search/test_search_loop.py::TestWorkflowEngineAbstraction -v # Engine protocols
pytest tests/scientist/search/test_search_loop.py::TestObjectives -v                # GDP growth, composite
pytest tests/scientist/search/test_search_loop.py::TestIntegration -v               # End-to-end search

# Специфические сценарии
pytest tests/scientist/search/test_search_loop.py -k "convergence" -v    # Convergence testing
pytest tests/scientist/search/test_search_loop.py -k "filtering" -v      # Two-stage filtering
pytest tests/scientist/search/test_search_loop.py -k "composite" -v      # Composite criteria
pytest tests/scientist/search/test_search_loop.py -k "engine" -v         # Workflow engines
```

## Связи с другими модулями

### Зависимости Search Layer

**Foundry Layer** (`foundry/`):
- **Expensive Stage**: Simulation execution для full evaluation
- **Calibration Results**: Optimization targets из calibration
- **Execution Engine**: JAX-based program execution

**Fabric Layer** (`fabric/`):
- **Trust Evaluation**: Simulation results validation
- **Evidence Bundles**: Result provenance tracking
- **Quality Indicators**: Data quality для simulation inputs

**IR Layer** (`ir/`):
- **Policy Candidates**: Generation новых policy variants
- **Semantic Validation**: Policy structure validation
- **Schema Evolution**: Compatibility между policy versions

**Core Layer** (`core/`):
- **Artifact Storage**: Persistence search results и intermediate policies
- **Canonical JSON**: Deterministic policy serialization
- **Environment Manifest**: Reproducible execution context

### Потребители Search Layer

**Scientist Layer** (`scientist/`):
- **Policy Refinement**: Iterative improvement generated policies
- **Optimization Pipeline**: Integration в full scientist workflow
- **Candidate Generation**: Protocol-based policy variant creation

**Integration Layer** (`integration/`):
- **End-to-End Optimization**: Full optimization workflows с calibration targets
- **LLM Integration**: AI-powered candidate generation
- **Workflow Orchestration**: Search integration в multi-agent pipelines

### Архитектурные инварианты

- **Закон O**: Optimization convergence (search loops converge к optimal policies или escalate)
- **Закон P**: Two-stage efficiency (cheap filtering prevents expensive evaluation waste)
- **Convergence Guarantee**: All search loops must converge или provide escalation path
- **Cost Optimization**: Cheap stage prevents expensive evaluation waste
- **Engine Abstraction**: WorkflowEngine protocol для seamless backend migration
- **Objective Normalization**: Unified minimization convention для all objectives
- **History Awareness**: Candidate generation considers previous iterations

## Разработка и расширение

### Добавление новых search тестов

1. **Optimization Flow**: Тестируйте convergence к known optima, stopping criteria triggers
2. **Two-Stage Filtering**: Проверяйте efficiency gains, rejection logic, stage coordination
3. **Stopping Criteria**: Тестируйте individual/composite criteria, trigger conditions
4. **Objective Functions**: Валидируйте evaluation logic, normalization, weighting
5. **Candidate Generation**: Проверяйте history awareness, convergence properties
6. **Workflow Engines**: Тестируйте protocol compliance, step execution, state management
7. Используйте fixtures для shared state (mock_candidate_generator, quadratic_objective, gdp_objective)

### Структура search теста

```python
def test_search_convergence_to_known_optimum(mock_candidate_generator, quadratic_objective):
    """Тестирование convergence к known optimum (x=0 для f(x)=x^2)."""
    from polisyos.scientist.search.controller import SearchController, SearchConfig
    from polisyos.scientist.search.stopping import MaxIterations

    def stage_a_evaluator(candidate, context):
        return 0.0, True  # Always pass cheap stage

    def stage_b_evaluator(candidate, context):
        x = candidate.get("x", 1.0)
        return {
            "simulation_results": {"x": x, "objective_value": x**2},
            "feedback": {"verdict": "APPROVE"}
        }

    config = SearchConfig(
        stopping=MaxIterations(20),
        objective=quadratic_objective,
    )

    controller = SearchController(
        config=config,
        candidate_generator=mock_candidate_generator,
        stage_a_evaluator=stage_a_evaluator,
        stage_b_evaluator=stage_b_evaluator,
    )

    result = controller.run({"user_request": "Minimize quadratic function"})

    # Verify: converged close to x=0
    assert result.best_candidate is not None
    assert abs(result.best_candidate["x"]) < 0.01, f"Failed to converge, best x: {result.best_candidate['x']}"
    assert result.best_objective < 0.001, f"Objective too high: {result.best_objective}"

def test_two_stage_filtering_prevents_expensive_calls(mock_candidate_generator, quadratic_objective):
    """Тестирование что Stage A rejection предотвращает Stage B вызовы."""
    from polisyos.scientist.search.controller import SearchController, SearchConfig
    from polisyos.scientist.search.stopping import MaxIterations

    stage_b_call_count = [0]

    def stage_a_evaluator(candidate, context):
        return 1.0, False  # Always reject in cheap stage

    def stage_b_evaluator(candidate, context):
        stage_b_call_count[0] += 1
        return {"simulation_results": {}, "feedback": {"verdict": "APPROVE"}}

    config = SearchConfig(
        stopping=MaxIterations(5),
        objective=quadratic_objective,
        enable_stage_a=True,
    )

    controller = SearchController(
        config=config,
        candidate_generator=mock_candidate_generator,
        stage_a_evaluator=stage_a_evaluator,
        stage_b_evaluator=stage_b_evaluator,
    )

    result = controller.run({"user_request": "Test filtering"})

    # Verify: Stage B never called due to Stage A rejection
    assert stage_b_call_count[0] == 0, "Stage B was called despite Stage A rejection!"
    assert result.stage_a_evaluations == 5
    assert result.stage_b_evaluations == 0

def test_composite_stopping_criteria():
    """Тестирование composite stopping criteria."""
    from polisyos.scientist.search.stopping import CompositeStoppingCriterion, MaxIterations, MaxWallTime
    import time

    composite = CompositeStoppingCriterion([
        MaxIterations(100),  # Won't trigger
        MaxWallTime(0.01),   # Will trigger after sleep
    ])

    history = [{"objective_value": 1.0} for _ in range(5)]

    # Sleep to trigger wall time criterion
    time.sleep(0.02)

    result = composite.check(history, {})

    assert result.should_stop, "Composite should stop when ANY criterion triggers"
    assert "wall_time" in result.details.get("triggered_by", "").lower()

def test_workflow_engine_step_execution():
    """Тестирование step-by-step выполнения SimpleLoopEngine."""
    from polisyos.scientist.workflow.engine_simple import SimpleLoopEngine

    execution_order = []

    def node_a(state):
        execution_order.append("a")
        return {**state, "phase": "a_completed"}

    def node_b(state):
        execution_order.append("b")
        return {**state, "phase": "b_completed"}

    def node_c(state):
        execution_order.append("c")
        return {**state, "phase": "c_completed"}

    engine = SimpleLoopEngine([
        ("node_a", node_a),
        ("node_b", node_b),
        ("node_c", node_c),
    ])

    # Test step-by-step execution
    state = {"initial": True}

    state, done = engine.step(state)
    assert execution_order == ["a"]
    assert state["phase"] == "a_completed"
    assert not done

    state, done = engine.step(state)
    assert execution_order == ["a", "b"]
    assert state["phase"] == "b_completed"
    assert not done

    state, done = engine.step(state)
    assert execution_order == ["a", "b", "c"]
    assert state["phase"] == "c_completed"
    assert done
```

## Troubleshooting

### Распространенные проблемы

**Search convergence failures:**
```bash
# Проверьте convergence к known optima
pytest tests/scientist/search/test_search_loop.py::TestOptimizationFlow::test_search_finds_quadratic_minimum -v
# Проверьте objective evaluation
pytest tests/scientist/search/test_search_loop.py::TestObjectives::test_gdp_objective_maximizes -v
```

**Two-stage filtering issues:**
```bash
# Проверьте что Stage A rejection prevents Stage B calls
pytest tests/scientist/search/test_search_loop.py::TestTwoStageFiltering::test_stage_a_rejection_skips_stage_b -v
# Проверьте Stage A evaluation logic
pytest tests/scientist/search/test_search_loop.py::TestTwoStageFiltering::test_cheap_stage_rejects_invalid_params -v
```

**Stopping criteria failures:**
```bash
# Проверьте MaxIterations stopping
pytest tests/scientist/search/test_search_loop.py::TestStoppingCriteria::test_max_iterations_stops_exactly -v
# Проверьте composite criteria
pytest tests/scientist/search/test_search_loop.py::TestStoppingCriteria::test_composite_stops_on_first_trigger -v
```

**Workflow engine issues:**
```bash
# Проверьте SimpleLoopEngine execution
pytest tests/scientist/search/test_search_loop.py::TestWorkflowEngineAbstraction::test_simple_engine_runs_to_completion -v
# Проверьте step-by-step execution
pytest tests/scientist/search/test_search_loop.py::TestWorkflowEngineAbstraction::test_simple_engine_step_by_step -v
```

**Objective evaluation issues:**
```bash
# Проверьте GDP objective logic
pytest tests/scientist/search/test_search_loop.py::TestObjectives::test_gdp_objective_maximizes -v
# Проверьте composite objectives
pytest tests/scientist/search/test_search_loop.py::TestObjectives::test_composite_objective_weighting -v
```

## Технологии и зависимости

### Core Dependencies
- **JAX**: Foundry execution для expensive stage evaluation
- **Core Artifacts**: Storage для search results и intermediate policies
- **IR Structures**: Policy candidates и semantic validation

### Search Infrastructure
- **SearchController**: Orchestrator для optimization loops
- **SearchConfig**: Configuration management для stopping criteria и objectives
- **CandidateGenerator Protocol**: Extensible interface для generation strategies
- **SearchResult**: Structured results с convergence tracking

### Optimization Components
- **Two-Stage Filtering**: Cheap/expensive evaluation pipeline
- **Stopping Criteria**: Composite termination conditions (iterations/wall-time/plateau)
- **Objective Functions**: GDP growth, inequality reduction, budget balance objectives
- **Workflow Engines**: Abstract engine protocol (SimpleLoop/LangGraph/Temporal/Prefect)

### Evaluation Components
- **Stage A Evaluator**: Fast rejection logic для invalid candidates
- **Stage B Evaluator**: Full simulation evaluation для valid candidates
- **Result Processing**: Feedback integration и objective calculation
- **History Tracking**: Iteration history для convergence analysis

### Integration Points
- **Foundry Simulation**: Expensive stage execution environment
- **Fabric Trust**: Result validation и evidence tracking
- **Core Persistence**: Artifact storage для reproducible optimization
