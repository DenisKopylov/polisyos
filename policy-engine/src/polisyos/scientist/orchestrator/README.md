# Orchestrator Layer: Управление жизненным циклом экспериментов

**Workflow orchestration и state management для сложных экспериментов**

Orchestrator Layer управляет полным жизненным циклом экспериментов с использованием LangGraph для декларативного workflow, обеспечивая reproducible execution и comprehensive state management.

## Обзор

Папка `orchestrator/` содержит ядро оркестрации экспериментов - workflow на LangGraph, state management, decision packets и вспомогательные компоненты для управления сложными multi-step экспериментами.

## Архитектура

```
orchestrator/
├── __init__.py                    # Пустой (для будущего использования)
├── workflow.py                   # Основной LangGraph workflow
├── state.py                      # ExperimentState и типы данных
├── flow_nodes.py                 # Реализации узлов workflow (1450+ строк)
├── decision_packet.py            # Итоговый артефакт эксперимента
├── decision_card.py              # Human-readable summaries результатов
├── run_record.py                 # Метаданные для воспроизводимости
├── run_timeline.py               # Timeline artifact для observability
├── audit.py                      # Система аудита и логирования
├── data_loader.py                # Загрузка данных из Fabric
├── nodes.py                      # Устаревшие узлы (deprecated)
├── optimizer.py                  # Оптимизация параметров (placeholder)
└── registry.py                   # Управление реестрами (placeholder)
```

## Компоненты

### 🔄 Workflow Orchestration (workflow.py)

Основной декларативный workflow на LangGraph с self-healing циклами:

#### build_workflow()
Создание LangGraph workflow:
```python
def build_workflow():
    """Создание основного scientist workflow."""
    workflow = StateGraph(ExperimentState)

    # Добавление узлов с phase management
    workflow.add_node("draft_ir", _with_phase(Phase.FRAME, draft_ir_node))
    workflow.add_node("validate_ir", _with_phase(Phase.FRAME, validate_ir_node))
    workflow.add_node("repair_ir", _with_phase(Phase.FRAME, repair_ir_node))
    workflow.add_node("compile_data_views", _with_phase(Phase.PLAN, compile_data_views_node))
    workflow.add_node("compile_model", _with_phase(Phase.EXECUTE, compile_model_node))
    workflow.add_node("train_agents", _with_phase(Phase.EXECUTE, train_agents_node))
    workflow.add_node("run_sim", _with_phase(Phase.EXECUTE, run_sim_node))
    workflow.add_node("analyze", _with_phase(Phase.EXECUTE, analyze_node))
    workflow.add_node("governor", _with_phase(Phase.POSTFLIGHT_GOV, governor_node))
    workflow.add_node("pack_decision", _with_phase(Phase.DECIDE, pack_decision_node))

    # Conditional edges для routing
    workflow.add_conditional_edges("validate_ir", _route_after_validate)
    workflow.add_conditional_edges("compile_model", _route_after_compile)
    workflow.add_conditional_edges("run_sim", _route_after_run_sim)

    workflow.set_entry_point("draft_ir")
    return workflow.compile()
```

#### Conditional Routing
Система условного routing на основе feedback:

```python
def _route_after_validate(state: ExperimentState) -> str:
    """Routing после валидации IR."""
    feedback = state.get("feedback")
    if feedback and feedback.get("verdict") == "NEEDS_REVISION":
        return "repair_ir"
    return "compile_data_views"

def _route_after_run_sim(state: ExperimentState) -> str:
    """Routing после симуляции."""
    feedback = state.get("feedback")
    if feedback:
        verdict = feedback.get("verdict")
        if verdict == "REJECT":
            return "pack_decision"
        if verdict == "NEEDS_REVISION":
            # Constraint errors → repair, runtime errors → pack_decision
            issues = feedback.get("issues", [])
            if any(issue.get("error_type") == "constraint" for issue in issues):
                return "pack_decision"
            return "repair_ir"
    return "analyze"
```

### 📊 State Management (state.py)

Центральная структура данных эксперимента:

#### ExperimentState
TypedDict с 90+ полями для полного state management:
```python
class ExperimentState(TypedDict):
    # Входные данные
    user_request: str
    ir: Optional[PolicySurfaceIR]
    last_ir_json: Optional[str]
    last_error: Optional[str]

    # Управление workflow
    optimize: Optional[bool]
    run_id: Optional[str]
    parent_run_id: Optional[str]
    repro_mode: Optional[str]
    run_record: Optional[RunRecord]
    budget: Optional[Dict[str, float]]
    budget_usage: Optional[Dict[str, float]]

    # Результаты симуляции
    simulation_results: Optional[Dict[str, float]]
    simulation_results_ref: Optional[Dict[str, Any]]
    fabric_result: Optional[Dict[str, Any]]

    # Обратная связь и governance
    feedback: Optional[GovernorFeedback]
    gate_request: Optional[Dict[str, Any]]
    gate_decision: Optional[Dict[str, Any]]

    # Audit и repair tracking
    audit_trail: List[Dict[str, Any]]
    repair_log: List[RepairAttempt]
    revision_count: int
    max_repair_attempts: int

    # И многое другое...
```

#### GovernorFeedback
Структура для обратной связи от governor:
```python
class GovernorFeedback(TypedDict):
    verdict: str  # "APPROVE", "REJECT", "NEEDS_REVISION"
    issues: List[Dict[str, Any]]  # Детали проблем
```

#### RepairAttempt
Отслеживание попыток исправления ошибок:
```python
class RepairAttempt(TypedDict):
    repair_attempt: int
    error_summary: str
    diff_before_after: Dict[str, Any]
```

### 🏗️ Flow Nodes (flow_nodes.py)

Реализации всех узлов workflow (1450+ строк кода):

#### draft_ir_node
Генерация политики из natural language:
```python
def draft_ir_node(state: ExperimentState) -> ExperimentState:
    """Генерация PolicySurfaceIR из user request."""
    # 1. Получение user_request
    # 2. Вызов drafter (LLM или MockAgent)
    # 3. Pydantic валидация
    # 4. Обновление state
    # 5. Audit logging
```

#### validate_ir_node
Полная валидация структуры и семантики:
```python
def validate_ir_node(state: ExperimentState) -> ExperimentState:
    """Валидация IR через validation pipeline."""
    # 1. Schema validation
    # 2. Semantic validation
    # 3. Business rules checking
    # 4. Governor feedback generation
```

#### compile_model_node
Компиляция политики в JAX:
```python
def compile_model_node(state: ExperimentState) -> ExperimentState:
    """Компиляция IR в executable model через Foundry."""
    # 1. Вызов foundry.compiler.compile_surface_policy
    # 2. Linker validation
    # 3. Artifact storage
    # 4. State updates
```

#### run_sim_node
Выполнение симуляции:
```python
def run_sim_node(state: ExperimentState) -> ExperimentState:
    """Запуск симуляции через compute layer."""
    # 1. Создание JobSpec
    # 2. Вызов compute.run_job
    # 3. Обработка результатов
    # 4. State updates
```

#### governor_node
Финальное решение:
```python
def governor_node(state: ExperimentState) -> ExperimentState:
    """Governor принимает финальное решение."""
    # 1. Анализ результатов
    # 2. Проверка бюджетов
    # 3. Safety validation
    # 4. Генерация verdict
```

### 📦 Decision Packet (decision_packet.py)

Итоговый артефакт эксперимента с полной информацией:

#### DecisionPacket
Структура финального результата:
```python
class DecisionPacket(BaseModel):
    schema_version: str = "1.0"
    generated_at: str
    run_id: str
    parent_run_id: Optional[str] = None
    run_record: RunRecord
    policy_ir: Optional[PolicySurfaceIR] = None
    simulation_results: Optional[Dict[str, Any]] = None
    fabric_result: Optional[FabricResult] = None
    feedback: Optional[GovernorFeedback] = None
    audit_trail: List[Dict[str, Any]] = []
    evidence_ref: EvidenceBundleRef | None = None
    uncertainty_ref: UncertaintyBoundsRef | None = None
```

### 🎯 Decision Card (decision_card.py)

Детерминированные human-readable summaries результатов экспериментов:

#### DecisionCard
Структура для презентации результатов:
```python
@dataclass
class DecisionCard:
    run_id: str
    generated_at: datetime
    schema_version: str = "1.0"

    verdict: str = Verdict.UNKNOWN
    confidence: str = Confidence.LOW

    policy_summary: str = "No policy defined"
    intervention_count: int = 0

    key_metrics: List[KeyMetric] = field(default_factory=list)
    issues: IssuesSummary = field(default_factory=lambda: IssuesSummary(0, 0, 0))

    total_duration_ms: int = 0
    phase_count: int = 0

    references: List[ArtifactReference] = field(default_factory=list)
    source_hash: Optional[str] = None
```

**Ключевые возможности:**
- Детерминированное создание из DecisionPacket
- Markdown rendering для отчетов
- Автоматическое извлечение key metrics (GDP, unemployment, etc.)
- Compliance summary с blocker/warning counts
- Artifact references для traceability
- Source hashing для reproducibility

#### Verdict и Confidence
```python
class Verdict:
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_REVISION = "NEEDS_REVISION"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"

class Confidence:
    HIGH = "HIGH"    # No blockers/warnings
    MEDIUM = "MEDIUM"  # Warnings present
    LOW = "LOW"     # Blockers present
```

### 📊 Run Timeline (run_timeline.py)

Timeline artifact для observability и tracing экспериментов:

#### RunTimeline
Append-only timeline с event tracking:
```python
@dataclass
class RunTimeline:
    run_id: str
    events: List[TimelineEvent] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Thread-safe recording
    _lock: RLock = field(default_factory=RLock)
```

#### TimelineEvent Types
```python
class TimelineEventType(Enum):
    RUN_START = "run_start"
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    NODE_ENTER = "node_enter"
    NODE_EXIT = "node_exit"
    ARTIFACT_CREATED = "artifact_created"
    VALIDATION_PASS = "validation_pass"
    VALIDATION_FAIL = "validation_fail"
    HUMAN_GATE = "human_gate"
    REFLEXION = "reflexion"
    ERROR = "error"
    RUN_END = "run_end"
```

**Ключевые возможности:**
- Thread-safe append-only recording
- Phase transition tracking с duration calculation
- Node execution timing
- Error и validation event aggregation
- Artifact creation tracking
- Export в core TraceRecord format

#### build_decision_packet()
Создание decision packet из experiment state:
```python
def build_decision_packet(state: ExperimentState, run_record: RunRecord) -> DecisionPacket:
    """Формирование итогового артефакта."""
    return DecisionPacket(
        run_id=run_record.run_id,
        run_record=run_record,
        policy_ir=state.get("ir"),
        simulation_results=state.get("simulation_results"),
        fabric_result=state.get("fabric_result"),
        evidence_ref=_resolve_evidence(state),
        uncertainty_ref=_resolve_uncertainty(state),
        feedback=state.get("feedback"),
        audit_trail=list(state.get("audit_trail", []))
    )
```

### 📋 Run Record (run_record.py)

Метаданные для полной воспроизводимости:

#### RunRecord
Детальная информация о прогоне:
```python
class RunRecord(BaseModel):
    run_id: str
    parent_run_id: Optional[str] = None
    seed: int
    repro_mode: ReproMode
    generator: Dict[str, str]
    python_version: str
    platform_info: Dict[str, str]
    library_versions: Dict[str, str]
    environment_vars: Dict[str, str]
    start_time: str
    end_time: Optional[str] = None
    status: str = "running"
```

#### build_run_record()
Создание run record с автоматическим сбором метаданных:
```python
def build_run_record(
    run_id: str,
    parent_run_id: Optional[str] = None,
    seed: int = 0,
    repro_mode: ReproMode = ReproMode.STRICT,
    generator: Optional[Dict[str, str]] = None
) -> RunRecord:
    """Создание run record с системной информацией."""
    return RunRecord(
        run_id=run_id,
        parent_run_id=parent_run_id,
        seed=seed,
        repro_mode=repro_mode,
        generator=generator or {"name": "policy-engine", "version": "0.1.0"},
        python_version=platform.python_version(),
        platform_info=get_platform_info(),
        library_versions=get_library_versions(),
        environment_vars=get_relevant_env_vars(),
        start_time=datetime.now(timezone.utc).isoformat()
    )
```

### 📝 Audit System (audit.py)

Комплексная система логирования всех операций:

#### append_audit()
Добавление события в audit trail:
```python
def append_audit(
    state: dict,
    operation: str,
    event_type: str,
    details: dict,
    timestamp: Optional[str] = None
) -> dict:
    """Добавление события аудита."""
    audit_entry = {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "event_type": event_type,
        "details": details,
        "phase": state.get("phase"),
        "run_id": state.get("run_id")
    }

    current_trail = state.get("audit_trail", [])
    current_trail.append(audit_entry)

    return {**state, "audit_trail": current_trail}
```

### 📊 Data Loader (data_loader.py)

Загрузка и подготовка данных из Fabric layer:

#### load_experiment_data()
Загрузка начальных данных для эксперимента:
```python
def load_experiment_data(state: ExperimentState) -> ExperimentState:
    """Загрузка данных из Fabric через SimulationDB и GraphStore."""
    # 1. Получение data view requests из IR
    # 2. Вызов fabric.io для загрузки данных
    # 3. Подготовка initial state snapshot
    # 4. Обновление state
```

## API Использование

### Запуск workflow

```python
from polisyos.scientist.orchestrator.workflow import build_workflow

# Создание workflow
workflow = build_workflow()

# Запуск эксперимента
result = workflow.invoke({
    "user_request": "Reduce poverty through targeted subsidies",
    "run_id": "experiment_001",
    "optimize": True,
    "budget": {
        "max_llm_calls": 3,
        "max_sim_runs": 1,
        "max_wall_time_s": 120
    }
})

# Получение результата
decision_packet = result.get("decision_packet")
if decision_packet:
    print(f"Verdict: {decision_packet.feedback.verdict}")
    print(f"Run ID: {decision_packet.run_id}")
```

### Работа с Decision Packet

```python
from polisyos.scientist.orchestrator.decision_packet import build_decision_packet

# Создание decision packet
packet = build_decision_packet(experiment_state, run_record)

# Сохранение (deprecated, использовать runtime.log_artifact)
# save_decision_packet(packet, base_dir=Path("results"))

# Доступ к результатам
print(f"Policy: {packet.policy_ir.semantic.interventions}")
print(f"Results: {packet.simulation_results}")
print(f"Audit events: {len(packet.audit_trail)}")
if packet.evidence_ref:
    print(f"Evidence bundle: {packet.evidence_ref.bundle_id}")
```

### Работа с Decision Card

```python
from polisyos.scientist.orchestrator.decision_card import DecisionCard, Verdict

# Создание из DecisionPacket
decision_card = DecisionCard.from_packet(decision_packet)

# Markdown отчет
markdown_report = decision_card.render_markdown()
print(markdown_report)

# Анализ результатов
print(f"Verdict: {decision_card.verdict}")
print(f"Confidence: {decision_card.confidence}")
print(f"Duration: {decision_card._format_duration()}")

# Key metrics
for metric in decision_card.key_metrics:
    print(f"{metric.name}: {metric.formatted} {metric.unit or ''}")

# Compliance status
issues = decision_card.issues
print(f"Blockers: {issues.blocker_count}, Warnings: {issues.warning_count}")
if issues.blocked_passes:
    print(f"Failed passes: {', '.join(issues.blocked_passes)}")

# Artifact references
for ref in decision_card.references:
    print(f"{ref.label}: {ref.ref}")

# Сериализация для storage
card_dict = decision_card.to_dict()
card_from_dict = DecisionCard.from_dict(card_dict)
```

### Работа с Run Timeline

```python
from polisyos.scientist.orchestrator.run_timeline import RunTimeline, TimelineEventType

# Создание timeline
timeline = RunTimeline(run_id="exp_001")

# Запуск эксперимента
timeline.record_run_start()
timeline.transition_phase("FRAME")

# Запись событий узлов
timeline.record(TimelineEventType.NODE_ENTER, "FRAME", node_id="draft_ir")
timeline.record(TimelineEventType.ARTIFACT_CREATED, "FRAME",
               artifact_ref="run/exp_001/policy_ir", node_id="draft_ir")
timeline.record(TimelineEventType.NODE_EXIT, "FRAME", node_id="draft_ir")

# Переход фаз
timeline.transition_phase("EXECUTE")
timeline.record(TimelineEventType.NODE_ENTER, "EXECUTE", node_id="run_sim")

# Запись ошибок
timeline.record(TimelineEventType.ERROR, "EXECUTE",
               node_id="run_sim", details={"error": "Simulation timeout"})

# Завершение
timeline.record_run_end(success=False)

# Анализ результатов
print(f"Total duration: {timeline.total_duration_ms}ms")
print(f"Phase durations: {timeline.get_phase_duration('FRAME')}ms")
print(f"Node durations: {timeline.get_node_durations()}")
print(f"Errors: {len(timeline.get_errors())}")
print(f"Artifacts created: {timeline.get_artifacts()}")
print(f"Validation summary: {timeline.get_validation_summary()}")

# Экспорт как artifact
timeline_artifact = timeline.to_artifact()

# Конвертация в TraceRecords для unified logging
trace_records = timeline.to_trace_records()
```

### Audit Trail анализ

```python
# Анализ audit trail
audit_events = decision_packet.audit_trail

# Статистика по операциям
operations = {}
for event in audit_events:
    op = event["operation"]
    operations[op] = operations.get(op, 0) + 1

print(f"Operations: {operations}")

# Timeline анализа
timestamps = [event["timestamp"] for event in audit_events]
duration = datetime.fromisoformat(timestamps[-1]) - datetime.fromisoformat(timestamps[0])
print(f"Total duration: {duration}")
```

## Расширение

### Кастомные узлы workflow

```python
from polisyos.scientist.orchestrator.state import ExperimentState

def custom_analysis_node(state: ExperimentState) -> ExperimentState:
    """Кастомный узел анализа."""

    results = state.get("simulation_results", {})

    # Кастомная логика анализа
    custom_metrics = {
        "efficiency_ratio": results.get("gdp_change", 0) / max(abs(results.get("budget_deficit", 1)), 1),
        "equity_score": 1 - results.get("gini_coefficient", 0),
        "sustainability_index": (results.get("gdp_change", 0) - abs(results.get("budget_deficit", 0))) / 100
    }

    return {**state, "custom_analysis": custom_metrics}
```

### Интеграция с DOE

```python
def doe_execution_node(state: ExperimentState) -> ExperimentState:
    """Узел для выполнения DoE дизайнов."""

    doe_design = state.get("doe_design")
    if not doe_design:
        return state

    # Выполнение multiple scenarios
    results = []
    for scenario in doe_design.get("scenarios", []):
        scenario_state = apply_scenario_to_state(state, scenario)
        scenario_result = run_single_scenario(scenario_state)
        results.append(scenario_result)

    # Statistical analysis
    analysis = analyze_doe_results(results)

    return {**state, "doe_results": results, "doe_analysis": analysis}
```

### Кастомные governor правила

```python
def custom_governor_logic(state: ExperimentState) -> GovernorFeedback:
    """Кастомная логика governor."""

    results = state.get("simulation_results", {})
    budget = state.get("budget", {})

    issues = []

    # Custom checks
    if results.get("budget_deficit", 0) < -1000:
        issues.append({
            "message": "Budget deficit exceeds threshold",
            "severity": "high",
            "code": "budget_deficit"
        })

    if results.get("unemployment_rate", 0) > 0.08:
        issues.append({
            "message": "Unemployment rate too high",
            "severity": "medium",
            "code": "high_unemployment"
        })

    verdict = "REJECT" if issues else "APPROVE"

    return GovernorFeedback(verdict=verdict, issues=issues)
```

## Тестирование

### Unit тесты

```bash
# Тестирование orchestrator компонентов
pytest tests/scientist/test_orchestrator_*.py -v

# Workflow execution
pytest tests/scientist/test_orchestrator_workflow.py -v

# State management
pytest tests/scientist/test_orchestrator_state.py -v

# Decision packets
pytest tests/scientist/test_orchestrator_decision_packet.py -v
```

### Integration тесты

```bash
# E2E workflow тесты
pytest tests/scientist/integration/test_workflow_smoke.py -v

# LLM integration тесты
pytest tests/scientist/integration/test_workflow_llm.py -v --tb=short
```

### Mock тестирование

```python
def test_workflow_execution_mock():
    """Тестирование workflow с mock компонентами."""

    # Создание mock state
    initial_state = {
        "user_request": "Test policy",
        "run_id": "mock_test_001",
        "budget": {"max_llm_calls": 1, "max_sim_runs": 1}
    }

    # Выполнение workflow
    workflow = build_workflow()
    result = workflow.invoke(initial_state)

    # Проверка результатов
    assert "decision_packet" in result
    packet = result["decision_packet"]
    assert packet.run_id == "mock_test_001"
```

## Связанные компоненты

- **Agent**: `draft_ir_node` использует `drafter.py`, Self-Healing system интегрируется с timeline events
- **Kernel**: FSM phases, guards, human gates - все transitions логируются в RunTimeline
- **Compute**: `run_sim_node` использует `run_job`, execution events tracked in timeline
- **Governance**: Preflight/postflight integration, validation passes create timeline events
- **IR**: PolicySurfaceIR валидация и compilation - results summarized in DecisionCard
- **Fabric**: Data loading и evidence bundles - references included in DecisionCard
- **Foundry**: Model compilation и simulation execution - artifacts tracked in timeline
- **Runtime**: Lifecycle management и artifact storage, DecisionCard и RunTimeline сохраняются как artifacts
- **Core**: TraceRecord integration через `timeline.to_trace_records()` для unified observability

## Troubleshooting

### Workflow не завершается

```
LangGraphError: Maximum iterations exceeded
```

**Решение**: Проверить self-healing циклы - возможно бесконечный loop в repair_ir

### State становится слишком большим

**Решение**: Очистить ненужные поля из state или использовать external storage для больших данных

### Decision packet не содержит ожидаемые данные

```
KeyError: 'simulation_results' not found in decision packet
```

**Решение**: Убедиться, что `run_sim_node` выполнился успешно перед `pack_decision_node`

### Audit trail поврежден

**Решение**: Проверить, что все узлы правильно вызывают `append_audit`

### Memory leaks в долгосрочных экспериментах

**Решение**: Implement state cleanup между итерациями или использовать streaming processing

### Race conditions в parallel execution

**Решение**: Implement proper synchronization primitives или sequential execution для critical sections