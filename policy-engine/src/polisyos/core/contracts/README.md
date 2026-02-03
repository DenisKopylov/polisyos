# Contracts (Типизированные контракты)

## Обзор

Типизированные контракты взаимодействия между модулями PolisyOS. Обеспечивают типобезопасность, стандартизацию интерфейсов и provenance tracking через строго типизированные ссылки на артефакты.

## Архитектура

```
contracts/
├── compiler.py     # CompileReportRef, LinkReportRef
├── fabric.py       # Fabric контракты (6 типов)
├── foundry.py      # Foundry контракты (15+ типов с patch-based state)
├── lex.py          # Lex (legal) контракты и RuleBackend protocol
├── legal.py        # DEPRECATED shim (реэкспорт lex)
├── scholar.py      # Scholar контракты (ResearchIntent, KnowledgeBundleRef)
├── scientist.py    # Scientist контракты (FailureCardRef, DecisionPacketRef, etc.)
└── trinity.py      # Trinity контракты (ProblemFrame, PolicySpec, ModelSpec)
```

## Принципы

Типизированные ссылки с `Literal` типами для kind/media_type, разделение данных и ссылок, строгая типизация с `extra="forbid"`.

## Compiler Contracts

### CompileReportRef

Ссылка на отчет компиляции политики.

```python
from polisyos.core.contracts.compiler import CompileReportRef

ref = CompileReportRef(
    artifact_id=artifact_id,
    kind="compiler.compile_report",  # literal type
    media_type="application/json"    # literal type
)
```

### LinkReportRef

Ссылка на отчет линковки программы.

```python
from polisyos.core.contracts.compiler import LinkReportRef

ref = LinkReportRef(
    artifact_id=artifact_id,
    kind="compiler.link_report",
    media_type="application/json"
)
```

## Fabric Contracts

Fabric предоставляет 7+ типов контрактов для обработки и агрегации данных.

### DataViewRequestRef

Запрос на представление данных из источника.

```python
from polisyos.core.contracts.fabric import DataViewRequestRef

request_ref = DataViewRequestRef(
    artifact_id=request_id,
    kind="ir.data_view_request",
    media_type="application/json"
)
```

### QueryPlan & QueryPlanRef

План запроса с шагами выполнения и метаданными.

```python
from polisyos.core.contracts.fabric import QueryPlan, QueryPlanRef, QueryPlanStep

# Модель данных плана запроса
plan = QueryPlan(
    request_ref=data_request_ref,
    engine="polisyos.fabric.v1",
    steps=[
        QueryPlanStep(op="filter", params={"condition": "amount > 1000"}),
        QueryPlanStep(op="aggregate", params={"group_by": "category", "metric": "sum"})
    ],
    trust_policy_id="strict_validation",
    notes=["Optimized for large datasets"]
)

# Типизированная ссылка
plan_ref = QueryPlanRef(
    artifact_id=plan_artifact_id,
    kind="fabric.query_plan",
    media_type="application/json"
)
```

### EvidenceBundle & EvidenceBundleRef

Пакет доказательств с трансформациями данных и provenance tracking.

```python
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef, EvidenceStep, ProvenanceCoreRefModel

# Пакет доказательств с provenance tracking и quality indicators
evidence = EvidenceBundle(
    sources=[source1_ref, source2_ref],
    transforms=[
        EvidenceStep(op="normalize", details={"method": "zscore"}),
        EvidenceStep(op="validate", details={"schema": "financial_data"})
    ],
    trust_policy_id="audited_sources",
    provenance_ref=ProvenanceCoreRefModel(
        graph_id="evidence_chain_001",
        stable_id="evidence_v2",
        artifact_id=provenance_artifact_id
    ),
    quality_indicators={
        "completeness": {"score": 0.95, "method": "coverage_analysis"},
        "consistency": {"score": 0.89, "method": "statistical_tests"},
        "timeliness": {"score": 0.92, "method": "freshness_check"}
    },
    notes=["All sources verified", "Statistical validation passed", "Provenance tracked", "Quality indicators computed"]
)

# Ссылка на пакет
evidence_ref = EvidenceBundleRef(
    artifact_id=evidence_id,
    kind="fabric.evidence_bundle",
    media_type="application/json"
)
```

### FabricResult & FabricResultRef

Результат обработки данных с полными метаданными.

```python
from polisyos.core.contracts.fabric import FabricResult, FabricResultRef

# Результат обработки
result = FabricResult(
    request_ref=data_request_ref,
    plan_ref=query_plan_ref,
    data_ref=processed_data_ref,
    data_schema_ref=schema_ref,
    sources=[source1_ref, source2_ref],
    trust_policy_id="enterprise_trust",
    evidence_ref=evidence_bundle_ref,
    uncertainty_ref=uncertainty_bounds_ref,
    warnings_ref=warnings_bundle_ref
)

# Типизированная ссылка
result_ref = FabricResultRef(
    artifact_id=result_id,
    kind="fabric.result_bundle",
    media_type="application/json"
)
```

### UncertaintyBounds & UncertaintyBoundsRef

Границы неопределенности для результатов обработки.

```python
from polisyos.core.contracts.fabric import UncertaintyBounds, UncertaintyBoundsRef
from decimal import Decimal

# Границы неопределенности
uncertainty = UncertaintyBounds(
    schema_version="1.0",
    value=Decimal("0.85"),
    lower=Decimal("0.82"),
    upper=Decimal("0.88"),
    method="two_pass_compare"
)

# Ссылка
uncertainty_ref = UncertaintyBoundsRef(
    artifact_id=uncertainty_id,
    kind="fabric.uncertainty_bounds",
    media_type="application/json"
)
```

### WarningsBundle & WarningsRef

Пакет предупреждений о потенциальных проблемах.

```python
from polisyos.core.contracts.fabric import WarningsBundle, WarningsRef
from polisyos.core.artifacts.manifest import WarningRecord

# Пакет предупреждений
warnings = WarningsBundle(
    warnings=[
        WarningRecord(
            code="DATA_QUALITY",
            msg="Missing values detected in 5% of records",
            data={"affected_columns": ["income"], "percentage": 5.0}
        ),
        WarningRecord(
            code="OUTLIER_DETECTED",
            msg="Statistical outliers found",
            data={"outlier_count": 23, "method": "iqr"}
        )
    ]
)

# Ссылка
warnings_ref = WarningsRef(
    artifact_id=warnings_id,
    kind="fabric.warnings",
    media_type="application/json"
)
```

### DataSnapshot & DataSnapshotRef

Фиксированный снапшот данных для воспроизводимых вычислений.

```python
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef

snapshot = DataSnapshot(
    data_ref=data_ref,
    data_schema_ref=data_schema_ref,
    evidence_ref=evidence_ref,
    uncertainty_ref=uncertainty_ref,
)

snapshot_ref = DataSnapshotRef(artifact_id=snapshot_id)
```

## Foundry Contracts

Foundry предоставляет 15+ типов контрактов для симуляции и исполнения политик, включая расширенные возможности conflict detection, cost modeling и runtime safety.

### PolicySurfaceIRRef

Ссылка на IR поверхности политики.

```python
from polisyos.core.contracts.foundry import PolicySurfaceIRRef

ref = PolicySurfaceIRRef(
    artifact_id=policy_ir_id,
    kind="ir.policy_surface",
    media_type="application/json"
)
```

### ProgramGraph & ProgramGraphRef

Граф программы с узлами и операциями.

```python
from polisyos.core.contracts.foundry import ProgramGraph, ProgramGraphRef, ProgramNode, ProgramOp

# Узел механизма
mechanism_node = ProgramNode(
    node_id="risk_assessment",
    node_kind="mechanism",
    mechanism_type="risk_calculator",
    params_ref=mechanism_params_ref,
    inputs=["user_data"],
    outputs=["risk_score"]
)

# Узел операции
operation_node = ProgramNode(
    node_id="decision_merge",
    node_kind="op",
    op=ProgramOp(
        op_kind="merge_state",
        params={"merge_strategy": "weighted_average"}
    ),
    inputs=["score1", "score2"],
    outputs=["final_decision"]
)

# Граф программы
graph = ProgramGraph(
    nodes=[mechanism_node, operation_node],
    edges=[{"from": "risk_assessment", "to": "decision_merge", "output": "risk_score"}],
    inputs=["user_data"],
    outputs=["final_decision"]
)

# Ссылка
graph_ref = ProgramGraphRef(
    artifact_id=graph_id,
    kind="foundry.program_graph",
    media_type="application/json"
)
```

### LoweredIR & LoweredIRRef

Пониженное IR для исполнения.

```python
from polisyos.core.contracts.foundry import LoweredIR, LoweredIRRef

# Пониженное IR
lowered = LoweredIR(
    source_graph_ref=program_graph_ref,
    target_platform="jax",
    optimized_ops=["vectorized_risk_calc", "parallel_merge"],
    metadata={"optimization_level": "aggressive", "platform_version": "0.4.25"}
)

# Ссылка
lowered_ref = LoweredIRRef(
    artifact_id=lowered_id,
    kind="foundry.lowered_ir",
    media_type="application/json"
)
```

### ExecPlan & ExecPlanRef

План исполнения с конфигурацией и environment tracking.

```python
from polisyos.core.contracts.foundry import ExecPlan, ExecPlanRef
from polisyos.core.artifacts.environment import EnvironmentManifestRef

# План исполнения с environment tracking, determinism tier и random seed
exec_plan = ExecPlan(
    program_ref=graph_ref,
    order=["init", "compute", "finalize"],
    environment_ref=EnvironmentManifestRef(
        artifact_id=env_id,
        kind="foundry.environment_manifest",
        media_type="application/json"
    ),
    environment_fingerprint="env_fingerprint_hash",
    determinism_tier="best_effort_gpu",
    random_seed=42,
    mode="perf",
    jit=True,
    max_steps=10000,
    notes=["Performance optimized execution with determinism guarantees"]
)

# Ссылка
exec_plan_ref = ExecPlanRef(
    artifact_id=plan_id,
    kind="foundry.exec_plan",
    media_type="application/json"
)
```

### AgentPolicyRef

Ссылка на артефакт обученной политики агента с метаданными обучения и determinism guarantees.

```python
from polisyos.core.contracts.foundry import AgentPolicyRef

policy_ref = AgentPolicyRef(
    artifact_id=policy_artifact_id,
    kind="foundry.agent_policy",
    media_type="application/octet-stream",
    policy_type="ActorCritic",
    determinism_tier="best_effort_gpu",
    training_steps=10000,
    env_hash="abcd1234efgh5678"
)
```

### State Management Contracts

#### StateSnapshot & StateSnapshotRef
```python
from polisyos.core.contracts.foundry import StateSnapshot, StateSnapshotRef

snapshot = StateSnapshot(
    simulation_time=1000,
    state_data_ref=state_data_ref,
    metadata={"checkpoint": True, "iteration": 500}
)

snapshot_ref = StateSnapshotRef(
    artifact_id=snapshot_id,
    kind="foundry.state_snapshot",
    media_type="application/json"
)
```

#### StateDelta & StateDeltaRef
```python
from polisyos.core.contracts.foundry import StateDelta, StateDeltaRef

# Patch-based state update
delta = StateDelta(
    base_snapshot_ref=previous_snapshot_ref,
    changes=[
        {"path": "user.123.balance", "op": "replace", "value": 1500.00},
        {"path": "system.risk_threshold", "op": "add", "value": 0.05}
    ],
    change_reason="Monthly balance update"
)

delta_ref = StateDeltaRef(
    artifact_id=delta_id,
    kind="foundry.state_delta",
    media_type="application/json"
)
```

### Configuration Contracts

#### TreasurySeed & TreasurySeedRef
```python
from polisyos.core.contracts.foundry import TreasurySeed, TreasurySeedRef

seed = TreasurySeed(
    seed_value="deterministic_seed_12345",
    algorithm="pcg64",
    entropy_source="secure_random"
)

seed_ref = TreasurySeedRef(
    artifact_id=seed_id,
    kind="foundry.treasury_seed",
    media_type="application/json"
)
```

#### ExecConfig & ExecConfigRef
```python
from polisyos.core.contracts.foundry import ExecConfig, ExecConfigRef

config = ExecConfig(
    platform="jax",
    version="0.4.25",
    device_config={"gpu": True, "cpu_threads": 8},
    optimization_flags=["enable_xla", "enable_64bit_precision"],
    random_seed=42
)

config_ref = ExecConfigRef(
    artifact_id=config_id,
    kind="foundry.exec_config",
    media_type="application/json"
)
```

#### AgentPolicyRef

```python
from polisyos.core.contracts.foundry import AgentPolicyRef

policy_ref = AgentPolicyRef(
    artifact_id=policy_artifact_id,
    kind="foundry.agent_policy",
    media_type="application/octet-stream",
    policy_type="ActorCritic",
    determinism_tier="best_effort_gpu",
    training_steps=10000,
    env_hash="abcd1234efgh5678"
)
```

### Monitoring Contracts

#### Metrics & MetricsRef
```python
from polisyos.core.contracts.foundry import Metrics, MetricsRef

metrics = Metrics(
    execution_time_seconds=45.2,
    memory_peak_gb=12.8,
    cpu_utilization_percent=85.5,
    gpu_utilization_percent=92.1,
    cache_hit_rate=0.78,
    custom_metrics={"convergence_rate": 0.95, "stability_score": 0.87}
)

metrics_ref = MetricsRef(
    artifact_id=metrics_id,
    kind="foundry.metrics",
    media_type="application/json"
)
```

#### TraceSliceRef
```python
from polisyos.core.contracts.foundry import TraceSliceRef

trace_ref = TraceSliceRef(
    artifact_id=trace_id,
    kind="foundry.trace_slice",
    media_type="application/jsonl"  # JSON Lines format
)
```

#### SimulationResult & SimulationResultRef
```python
from polisyos.core.contracts.foundry import SimulationResult, SimulationResultRef

result = SimulationResult(
    exec_plan_ref=exec_plan_ref,
    metrics_ref=metrics_ref,
    state_snapshot_ref=state_snapshot_ref,
    environment_ref=environment_ref,
    trace_slice_ref=trace_ref,
)

result_ref = SimulationResultRef(artifact_id=simulation_result_id)
```

### Validation Contracts

#### ConstraintReportRef
```python
from polisyos.core.contracts.foundry import ConstraintReportRef

constraint_ref = ConstraintReportRef(
    artifact_id=constraint_id,
    kind="foundry.constraint_report",
    media_type="application/json"
)
```

#### CalibrationReportRef
```python
from polisyos.core.contracts.foundry import CalibrationReportRef

calibration_ref = CalibrationReportRef(
    artifact_id=calibration_id,
    kind="foundry.calibration_report",
    media_type="application/json"
)
```

### Patch-based State Management Contracts

Современная система управления состоянием с patch-based updates, confidence scoring и метаданными.

#### PatchOp & UpdateOp

```python
from polisyos.core.contracts.foundry import PatchOp, UpdateOp

# Patch operation для обновления состояния агентов
patch_op = PatchOp(
    slot_id="agent_balance",
    op="add",
    value_ref=balance_update_ref,
    mask_scope="per_agent",
    notes=["Monthly interest payment"]
)

# Update operation с расширенными опциями
update_op = UpdateOp(
    slot_id="market_price",
    op="clamp",
    value_ref=new_price_ref,
    mask_ref=agent_mask_ref,
    priority=3,
    min_ref=min_price_ref,
    max_ref=max_price_ref,
    notes=["Price stabilization within bounds"]
)
```

#### Patch & PatchSet

```python
from polisyos.core.contracts.foundry import Patch, PatchSet, PatchMeta

# Patch с метаданными и confidence scoring
patch = Patch(
    schema_version="1.0",
    meta=PatchMeta(
        source_node_id="economic_mechanism_001",
        step=750,
        mode="perf",
        confidence=0.89,
        tags=["economic_update", "price_mechanism"],
        notes=["Market equilibrium adjustment"]
    ),
    ops=[update_op],
    notes=["Economic state update with market corrections"]
)

# PatchSet для batch updates
patch_set = PatchSet(
    schema_version="1.0",
    patches=[patch],
    notes=["Quarterly economic adjustments"]
)
```

### Advanced Foundry Runtime Contracts

Современные контракты Foundry включают расширенные возможности для compile-time validation, cost estimation и runtime safety, обеспечивая надежное и эффективное исполнение сложных симуляций.

#### Conflict Detection Contracts

**Назначение**: Контракты для результатов анализа конфликтов в ProgramGraph с actionable insights для разработчиков.

##### SlotConflict

```python
from polisyos.foundry.conflict_checker import SlotConflict

conflict = SlotConflict(
    slot_id="user_balance",
    writers=frozenset(["credit_mechanism", "debit_mechanism"]),
    conflict_kind=MergeConflictKind.CONCURRENT_WRITE,
    location="program_graph.nodes[3]",
    suggestion="Consider using atomic operations or sequential execution",
    severity="blocker"
)
```

##### ConflictReport

```python
from polisyos.foundry.conflict_checker import ConflictReport

report = ConflictReport(
    schema_version="1.0",
    ok=False,
    conflicts=[conflict],
    analysis_time_ms=45,
    program_graph_fingerprint="abc123...",
    recommendations=["Split conflicting mechanisms", "Use merge rules"]
)
```

#### Cost Modeling Contracts

**Назначение**: Контракты для оценки и управления стоимостью исполнения программ с budget tracking.

##### CostEstimate

```python
from polisyos.foundry.cost_model import CostEstimate

estimate = CostEstimate(
    estimated_compile_ms=2500,
    estimated_run_ms=75,
    estimated_total_ms=2575,
    estimated_memory_mb=512,
    estimated_flops=500_000,
    per_mechanism_costs={
        "risk_mechanism": 1200,
        "pricing_mechanism": 800,
        "validation_mechanism": 575
    },
    exceeds_budget=False,
    budget_utilization=0.85,
    confidence="high"
)
```

##### CostBudget

```python
from polisyos.foundry.cost_model import CostBudget

budget = CostBudget(
    max_compile_ms=5000,
    max_run_ms=100,
    max_memory_mb=1024,
    max_flops=1_000_000,
    priority="performance",
    tags=["simulation", "production"]
)
```

#### NaN Guard Contracts

**Назначение**: Контракты для диагностики и отчетности о NaN/Inf значениях в runtime.

##### NaNDiagnostic

```python
from polisyos.foundry.runtime.nan_guard import NaNDiagnostic

diagnostic = NaNDiagnostic(
    slot_id="market_price",
    mechanism_id="pricing_mechanism",
    time_step=150,
    nan_count=3,
    inf_count=0,
    sample_indices=[42, 87, 156],
    possible_cause="Division by zero in price calculation",
    value_stats={"mean": 45.2, "std": 12.8, "min": 0.0, "max": 89.5}
)
```

##### NaNGuardReport

```python
from polisyos.foundry.runtime.nan_guard import NaNGuardReport

report = NaNGuardReport(
    schema_version="1.0",
    ok=False,
    diagnostics=[diagnostic],
    checks_performed=150,
    first_failure_step=150
)
```

## Trinity Contracts (Базовые спецификации)

Trinity контракты определяют ссылки на три фундаментальные спецификации системы PolisyOS: ProblemFrame (проблема), PolicySpec (политика), ModelSpec (модель). Эти контракты обеспечивают структурированный подход к экспериментам и политикам, следуя паттерну "триединства" для разделения concerns между "Почему" (ProblemFrame), "Что" (PolicySpec) и "Как" (ModelSpec).

### ProblemFrameRef

Ссылка на спецификацию проблемы (ProblemFrame) - определение контекста и требований к политике.

```python
from polisyos.core.contracts.trinity import ProblemFrameRef

problem_ref = ProblemFrameRef(
    artifact_id=problem_frame_id,
    kind="ir.problem_frame",        # literal type
    media_type="application/json"   # literal type
)
```

### PolicySpecRef

Ссылка на спецификацию политики (PolicySpec) - определение структуры и поведения политики.

```python
from polisyos.core.contracts.trinity import PolicySpecRef

policy_ref = PolicySpecRef(
    artifact_id=policy_spec_id,
    kind="ir.policy_spec",          # literal type
    media_type="application/json"   # literal type
)
```

### ModelSpecRef

Ссылка на спецификацию модели (ModelSpec) - определение модели мира и ее компонентов.

```python
from polisyos.core.contracts.trinity import ModelSpecRef

model_ref = ModelSpecRef(
    artifact_id=model_spec_id,
    kind="ir.model_spec",           # literal type
    media_type="application/json"   # literal type
)
```

### TrinityBundle & TrinityBundleRef

Полный bundle трёх спецификаций и ссылка на bundle как артефакт.

```python
from polisyos.core.contracts.trinity import TrinityBundle, TrinityBundleRef

bundle = TrinityBundle(
    problem_frame_ref=problem_ref,
    policy_spec_ref=policy_ref,
    model_spec_ref=model_ref,
)

bundle_ref = TrinityBundleRef(artifact_id=bundle_id)
```

## Scientist Contracts (Контракты Scientist)

Scientist контракты определяют типизированные ссылки на артефакты, используемые в Scientist layer для оркестрации экспериментов, оценки политик и управления жизненным циклом ИИ-агентов. Эти контракты наследуются от базового класса ArtifactRef и обеспечивают типобезопасное взаимодействие.

### ScientistArtifactRef (Базовый класс)

Базовый класс для всех ссылок на артефакты в Scientist layer.

```python
from polisyos.core.contracts.scientist import ScientistArtifactRef

artifact_ref = ScientistArtifactRef(
    artifact_id="sha256:abcd1234...",
    kind="scientist.policy_ir",
    media_type="application/json",
)
```

### ExperimentStateRef

Ссылка на экспериментальное состояние (snapshot) как артефакт.

```python
from polisyos.core.contracts.scientist import ExperimentStateRef

state_ref = ExperimentStateRef(artifact_id="sha256:state...")
```

### DecisionPacketRef

Ссылка на DecisionPacket артефакт.

```python
from polisyos.core.contracts.scientist import DecisionPacketRef

decision_ref = DecisionPacketRef(artifact_id="sha256:packet...")
```

### FailureCardRef

Ссылка на FailureCard артефакт, содержащий информацию об ошибках и неудачах.

```python
from polisyos.core.contracts.scientist import FailureCardRef

failure_ref = FailureCardRef(
    artifact_id="sha256:abcd1234...",
    attempt_number=3,
    error_code="VALIDATION_ERROR",
    source_step="policy_compilation",
    can_retry=True,
)
```

### PolicyIRRef

Ссылка на PolicySurfaceIR артефакт с информацией о версии и статусе.

```python
from polisyos.core.contracts.scientist import PolicyIRRef

policy_ir_ref = PolicyIRRef(
    artifact_id="sha256:efgh5678...",
    version=2,
    status="validated",
)
```

### CritiqueRef

Ссылка на артефакт оценки критика (Critic evaluation).

```python
from polisyos.core.contracts.scientist import CritiqueRef

critique_ref = CritiqueRef(
    artifact_id="sha256:ijkl9012...",
    verdict="revise",
    ir_ref="sha256:efgh5678...",
)
```

### TimelineRef

Ссылка на RunTimeline артефакт с метаданными о событиях эксперимента.

```python
from polisyos.core.contracts.scientist import TimelineRef

timeline_ref = TimelineRef(
    artifact_id="sha256:abcd1234...",
    run_id="exp_001_20241215",
    event_count=150,
    total_duration_ms=45000,
)
```
### DecisionCardRef

Ссылка на DecisionCard артефакт - детерминированную сводку результатов эксперимента.

```python
from polisyos.core.contracts.scientist import DecisionCardRef

card_ref = DecisionCardRef(
    artifact_id="sha256:efgh5678...",
    run_id="exp_001_20241215",                 # ID эксперимента
    verdict="APPROVE",                         # вердикт оценки
    generated_at="2024-12-15T14:30:00Z"        # время генерации
)
```

### ProblemFrameRef

Ссылка на спецификацию проблемы (ProblemFrame) - определение контекста и требований к политике.

```python
from polisyos.core.contracts.trinity import ProblemFrameRef

problem_ref = ProblemFrameRef(
    artifact_id=problem_frame_id,
    kind="ir.problem_frame",        # literal type
    media_type="application/json"   # literal type
)
```

### PolicySpecRef

Ссылка на спецификацию политики (PolicySpec) - определение структуры и поведения политики.

```python
from polisyos.core.contracts.trinity import PolicySpecRef

policy_ref = PolicySpecRef(
    artifact_id=policy_spec_id,
    kind="ir.policy_spec",          # literal type
    media_type="application/json"   # literal type
)
```

### ModelSpecRef

Ссылка на спецификацию модели (ModelSpec) - определение модели мира и ее компонентов.

```python
from polisyos.core.contracts.trinity import ModelSpecRef

model_ref = ModelSpecRef(
    artifact_id=model_spec_id,
    kind="ir.model_spec",           # literal type
    media_type="application/json"   # literal type
)
```

## Lex Contracts (Контракты Lex)

Lex контракты определяют интерфейсы для compliance-валидации политик и интеграции с pluggable rule backends.
`polisyos.core.contracts.legal` является DEPRECATED shim и реэкспортирует `polisyos.core.contracts.lex`.

### ComplianceIssue & IssueSeverity

```python
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity

issue = ComplianceIssue(
    pass_id="legal",
    path=["policy", "budget"],
    message="Budget deficit exceeds 5%",
    severity=IssueSeverity.BLOCKER,
    code="BUDGET_DEFICIT",
)
```

### RuleBackend

```python
from polisyos.core.contracts.lex import RuleBackend, ComplianceIssue
from polisyos.core.contracts.lex import NormPack

class CustomRuleBackend(RuleBackend):
    @property
    def backend_id(self) -> str:
        return "custom.v1"

    def evaluate(self, norm_pack: NormPack, context: dict) -> list[ComplianceIssue]:
        return []
```

### LegalContext

```python
from polisyos.core.contracts.lex import LegalContext, FoundryRefs
from polisyos.core.contracts.trinity import TrinityBundle
from polisyos.core.contracts.fabric import FabricResultRef
from polisyos.core.contracts.foundry import ExecPlanRef, SimulationResultRef

ctx = LegalContext(
    trinity=TrinityBundle(
        problem_frame_ref=problem_frame_ref,
        policy_spec_ref=policy_spec_ref,
        model_spec_ref=model_spec_ref,
    ),
    fabric_results=[FabricResultRef(artifact_id=fabric_result_id)],
    foundry=FoundryRefs(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_id),
        simulation_result_ref=SimulationResultRef(artifact_id=sim_result_id),
    ),
    jurisdiction="US-CA",
    as_of_date="2026-02-03",
    norm_pack_ref=norm_pack_ref,
)
```

### LegalReportRef & ChangeProposalRef

```python
from polisyos.core.contracts.lex import LegalReportRef, ChangeProposalRef

report_ref = LegalReportRef(artifact_id=report_id)
proposal_ref = ChangeProposalRef(artifact_id=proposal_id)
```

## Scholar Contracts (Контракты Scholar)

Scholar контракты задают ABI-стык для исследовательского обогащения (без реализации Scholar).

### ResearchIntent

```python
from polisyos.core.contracts.scholar import ResearchIntent, TimeWindow

intent = ResearchIntent(
    domain="labor",
    topic="minimum_wage",
    jurisdictions=["US-CA"],
    time_window=TimeWindow(start="2020-01-01", end="2025-12-31"),
    required_outputs=["docs", "claims", "bundles"],
    budgets={"max_docs": 200},
)
```

### KnowledgeBundleRef

```python
from polisyos.core.contracts.scholar import KnowledgeBundleRef

bundle_ref = KnowledgeBundleRef(artifact_id=bundle_id)
```

## Производительность

- **Типизация**: Compile-time проверки без runtime overhead
- **Валидация**: Эффективная Pydantic валидация
- **Хранение**: JSON сериализация с оптимизацией
- **Доступ**: CAS обеспечивает быстрое чтение/запись
- **Trinity contracts**: Легковесные ссылки без дополнительных накладных расходов
- **Bundle validation**: Быстрая проверка совместимости Trinity спецификаций

## Лучшие практики

1. **Используйте типизированные ссылки**: Всегда создавайте конкретные Ref классы вместо общего ArtifactRef
2. **Валидируйте данные**: Проверяйте целостность контрактов при загрузке
3. **Поддерживайте provenance**: Связывайте артефакты через ссылки на входы
4. **Документируйте контракты**: Описывайте назначение и constraints каждого контракта
5. **Версионируйте схемы**: Используйте семантическое версионирование для моделей данных
6. **Используйте Scientist контракты для экспериментов**: Для управления жизненным циклом политик и отслеживания оценок используйте PolicyIRRef, CritiqueRef и FailureCardRef
7. **Применяйте conflict detection**: Всегда анализируйте ProgramGraph на конфликты перед запуском симуляций
8. **Используйте cost modeling**: Планируйте исполнение с учетом бюджетов на ресурсы и время
9. **Внедряйте NaN guard**: Защищайте симуляции от numerical instability с помощью runtime проверок
10. **Интегрируйте advanced contracts**: Используйте новые контракты Foundry для compile-time validation и runtime safety
