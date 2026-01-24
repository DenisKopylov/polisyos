# Contracts Module (Контракты)

## Обзор

Модуль `contracts` определяет типизированные контракты взаимодействия между различными модулями системы PolisyOS. Контракты обеспечивают типобезопасность, стандартизацию интерфейсов и четкое разделение ответственности между модулями через строго типизированные ссылки на артефакты.

## Архитектура

```
contracts/
├── __init__.py     # Экспорт всех контрактов
├── compiler.py     # Контракты компилятора
├── fabric.py       # Контракты Fabric (обработка данных)
└── foundry.py      # Контракты Foundry (симуляция)
```

## Принципы контрактов

### Типизированные ссылки

Все контракты наследуются от `ArtifactRef` с литеральными типами для kind и media_type:

```python
class FabricResultRef(ArtifactRef):
    kind: Literal["fabric.result_bundle"] = "fabric.result_bundle"
    media_type: Literal["application/json"] = "application/json"
```

### Разделение данных и ссылок

- **ArtifactRef**: Ссылка на артефакт с типизацией
- **Модели данных**: Структурированные данные (Pydantic модели)

### Строгая типизация

- `extra="forbid"` предотвращает неожиданные поля
- Литеральные типы для compile-time проверок
- Валидация через Pydantic

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

Fabric предоставляет 6 типов контрактов для обработки и агрегации данных.

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

Пакет доказательств с трансформациями данных.

```python
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef, EvidenceStep

# Пакет доказательств
evidence = EvidenceBundle(
    sources=[source1_ref, source2_ref],
    transforms=[
        EvidenceStep(op="normalize", details={"method": "zscore"}),
        EvidenceStep(op="validate", details={"schema": "financial_data"})
    ],
    trust_policy_id="audited_sources",
    notes=["All sources verified", "Statistical validation passed"]
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

## Foundry Contracts

Foundry предоставляет 13 типов контрактов для симуляции и исполнения политик.

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

План исполнения с конфигурацией.

```python
from polisyos.core.contracts.foundry import ExecPlan, ExecPlanRef

# План исполнения
exec_plan = ExecPlan(
    program_graph_ref=graph_ref,
    exec_config_ref=config_ref,
    resource_requirements={
        "cpu_cores": 8,
        "memory_gb": 32,
        "gpu_memory_gb": 16
    },
    optimization_hints=["enable_xla", "fuse_operations"],
    timeout_seconds=3600
)

# Ссылка
exec_plan_ref = ExecPlanRef(
    artifact_id=plan_id,
    kind="foundry.exec_plan",
    media_type="application/json"
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

## Использование контрактов

### Создание типизированных ссылок

```python
from polisyos.core.contracts.fabric import FabricResultRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import FabricResult

# Сохранение результата
store = FileSystemCAS(Path("/tmp/artifacts"))
result_data = FabricResult(...)

result_ref = store.put_json(
    result_data.model_dump(),
    PutOptions(
        kind="fabric.result_bundle",
        media_type="application/json",
        # ... другие опции
    )
)

# Создание типизированной ссылки
typed_ref = FabricResultRef.from_artifact_ref(result_ref)
```

### Валидация контрактов

```python
def validate_fabric_result(store: FileSystemCAS, ref: FabricResultRef) -> bool:
    """Валидация FabricResult контракта"""

    # Загрузка данных
    data = store.get_json(ref.artifact_id)
    result = FabricResult(**data)

    # Проверка обязательных ссылок
    required_refs = [
        result.request_ref,
        result.plan_ref,
        result.data_ref,
        result.evidence_ref
    ]

    if any(ref is None for ref in required_refs):
        return False

    # Проверка существования артефактов
    for artifact_ref in required_refs:
        if artifact_ref is not None and not store.has(artifact_ref.artifact_id):
            return False

    return True
```

### Работа с provenance

```python
def trace_fabric_lineage(store: FileSystemCAS, result_ref: FabricResultRef) -> dict:
    """Трассировка происхождения Fabric результата"""

    result = FabricResult(**store.get_json(result_ref.artifact_id))

    lineage = {
        "result": str(result_ref.artifact_id),
        "request": str(result.request_ref.artifact_id) if result.request_ref else None,
        "plan": str(result.plan_ref.artifact_id) if result.plan_ref else None,
        "data_sources": [
            str(src.artifact_id) for src in result.sources
        ],
        "evidence": str(result.evidence_ref.artifact_id) if result.evidence_ref else None
    }

    return lineage
```

## Архитектурная роль

### Разделение ответственности

- **Contracts**: Определяют интерфейсы и типы данных
- **Artifacts**: Предоставляют инфраструктуру хранения
- **Модули**: Реализуют логику, используя контракты

### Типобезопасность

```python
# Compile-time проверка типов
def process_fabric_result(ref: FabricResultRef) -> None:
    # ref гарантированно имеет kind="fabric.result_bundle"
    # и media_type="application/json"
    pass

# Runtime валидация
result = FabricResult(**data)  # Pydantic validation
```

### Межмодульное взаимодействие

```python
# Foundry получает результат от Fabric
fabric_result = FabricResultRef(...)  # из Fabric

# Foundry использует данные для симуляции
state = StateSnapshot(
    simulation_time=0,
    state_data_ref=fabric_result.artifact_id,  # provenance link
    metadata={"source": "fabric_ingestion"}
)
```

## Производительность

- **Типизация**: Compile-time проверки без runtime overhead
- **Валидация**: Эффективная Pydantic валидация
- **Хранение**: JSON сериализация с оптимизацией
- **Доступ**: CAS обеспечивает быстрое чтение/запись

## Лучшие практики

1. **Используйте типизированные ссылки**: Всегда создавайте конкретные Ref классы вместо общего ArtifactRef
2. **Валидируйте данные**: Проверяйте целостность контрактов при загрузке
3. **Поддерживайте provenance**: Связывайте артефакты через ссылки на входы
4. **Документируйте контракты**: Описывайте назначение и constraints каждого контракта
5. **Версионируйте схемы**: Используйте семантическое версионирование для моделей данных