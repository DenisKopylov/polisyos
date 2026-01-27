# Contracts Module (Контракты)

## Обзор

Модуль `contracts` определяет типизированные контракты взаимодействия между различными модулями системы PolisyOS. Контракты обеспечивают типобезопасность, стандартизацию интерфейсов и четкое разделение ответственности между модулями через строго типизированные ссылки на артефакты.

## Архитектура

```
contracts/
├── __init__.py     # Экспорт всех контрактов
├── compiler.py     # Контракты компилятора
├── fabric.py       # Контракты Fabric (обработка данных)
├── foundry.py      # Контракты Foundry (симуляция)
├── legal.py        # Legal compliance контракты
├── scientist.py    # Контракты Scientist (эксперименты и агенты)
└── trinity.py      # Trinity контракты (базовые спецификации)
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

Пакет доказательств с трансформациями данных и provenance tracking.

```python
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef, EvidenceStep, ProvenanceCoreRefModel

# Пакет доказательств с provenance tracking
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
    notes=["All sources verified", "Statistical validation passed", "Provenance tracked"]
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

План исполнения с конфигурацией и environment tracking.

```python
from polisyos.core.contracts.foundry import ExecPlan, ExecPlanRef
from polisyos.core.artifacts.environment import EnvironmentManifestRef

# План исполнения с environment tracking
exec_plan = ExecPlan(
    program_ref=graph_ref,
    order=["init", "compute", "finalize"],
    environment_ref=EnvironmentManifestRef(
        artifact_id=env_id,
        kind="foundry.environment_manifest",
        media_type="application/json"
    ),
    mode="perf",
    jit=True,
    max_steps=10000,
    notes=["Performance optimized execution"]
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

## Trinity Contracts (Базовые спецификации)

Trinity контракты определяют ссылки на три фундаментальные спецификации системы PolisyOS: ProblemFrame (проблема), PolicySpec (политика), ModelSpec (модель). Эти контракты обеспечивают структурированный подход к экспериментам и политикам.

## Scientist Contracts (Контракты Scientist)

Scientist контракты определяют типизированные ссылки на артефакты, используемые в Scientist layer для оркестрации экспериментов, оценки политик и управления жизненным циклом ИИ-агентов. Эти контракты наследуются от базового класса ArtifactRef и обеспечивают типобезопасное взаимодействие.

### ArtifactRef (Базовый класс)

Базовый класс для всех ссылок на артефакты в Scientist layer с CAS хешированием.

```python
from polisyos.core.contracts.scientist import ArtifactRef

# Базовый класс для всех scientist ссылок
artifact_ref = ArtifactRef(
    ref_type="policy_ir",                      # Тип ссылки
    cas_hash="sha256:abcd1234...",           # Content-addressable hash
    artifact_type="policy_ir"                 # Тип артефакта
)
```

### FailureCardRef

Ссылка на FailureCard артефакт, содержащий информацию об ошибках и неудачах в процессе выполнения экспериментов.

```python
from polisyos.core.contracts.scientist import FailureCardRef

failure_ref = FailureCardRef(
    ref_type="failure_card",
    cas_hash="sha256:abcd1234...",
    artifact_type="failure_card",
    attempt_number=3,                          # номер попытки (≥1)
    error_code="VALIDATION_ERROR",             # код ошибки для категоризации
    source_step="policy_compilation",          # источник ошибки
    can_retry=True                             # можно ли повторить
)
```

### PolicyIRRef

Ссылка на PolicySurfaceIR артефакт с информацией о версии и статусе.

```python
from polisyos.core.contracts.scientist import PolicyIRRef

policy_ir_ref = PolicyIRRef(
    ref_type="policy_ir",
    cas_hash="sha256:efgh5678...",
    artifact_type="policy_ir",
    version=2,                                 # номер ревизии (≥1)
    status="validated"                         # статус: draft, validated, rejected
)
```

### CritiqueRef

Ссылка на артефакт оценки критика (Critic evaluation) с вердиктом и ссылкой на оцененный IR.

```python
from polisyos.core.contracts.scientist import CritiqueRef

critique_ref = CritiqueRef(
    ref_type="critique",
    cas_hash="sha256:ijkl9012...",
    artifact_type="critique",
    verdict="revise",                          # вердикт: approve, revise, reject
    ir_ref="sha256:efgh5678..."               # хеш оцененного IR
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

## Legal Contracts (Контракты Legal)

Legal контракты определяют интерфейсы для compliance валидации политик и интеграции с pluggable rule backends. Эти контракты обеспечивают стандартизацию legal validation в системе PolisyOS.

### NormPack

Пакет нормативных правил и ограничений для валидации политик.

```python
from polisyos.ir.norm_pack import NormPack

# Создание пакета норм
norm_pack = NormPack(
    schema_version="1.0",
    norms=[
        NormRule(
            rule_id="budget_deficit_limit",
            rule_type=RuleType.CONSTRAINT,
            description="Бюджетный дефицит не должен превышать 5%",
            expression="budget_deficit <= 0.05"
        )
    ]
)
```

### NormRef

Ссылка на нормативное правило в системе артефактов.

```python
from polisyos.ir.norm_pack import NormRef

norm_ref = NormRef(
    rule_id="budget_deficit_limit",
    version="1.0"
)
```

### NormRule

Определение отдельного нормативного правила с логикой валидации.

```python
from polisyos.ir.norm_pack import NormRule, RuleType

rule = NormRule(
    rule_id="privacy_data_retention",
    rule_type=RuleType.PRIVACY,
    description="Персональные данные должны храниться не более 7 лет",
    expression="data_retention_days <= 2555",  # 7 * 365
    severity="high"
)
```

### RuleType

Типы нормативных правил для категоризации.

```python
from polisyos.ir.norm_pack import RuleType

# Доступные типы правил
types = [
    RuleType.CONSTRAINT,    # Ограничения на параметры политики
    RuleType.PRIVACY,       # Правила приватности данных
    RuleType.ETHICS,        # Этические ограничения
    RuleType.LEGAL,         # Правовые требования
    RuleType.SAFETY         # Правила безопасности
]
```

### RuleBackend

Интерфейс для реализации движков валидации правил.

```python
from polisyos.scientist.governance.legal.backends.base import RuleBackend

class CustomRuleBackend(RuleBackend):
    """Кастомный backend для валидации правил."""

    def validate_rule(self, rule: NormRule, context: dict) -> ValidationResult:
        """Валидация отдельного правила."""
        # Реализация логики валидации
        pass

    def validate_pack(self, norm_pack: NormPack, context: dict) -> list[ValidationResult]:
        """Валидация пакета норм."""
        # Реализация логики валидации пакета
        pass
```

### TrinityBundle

Пакет содержащий ссылки на все три Trinity артефакта с информацией о совместимости.

```python
from polisyos.core.contracts.trinity import TrinityBundle

# Создание Trinity bundle для эксперимента
trinity_bundle = TrinityBundle(
    problem_frame_ref=problem_ref,
    policy_spec_ref=policy_ref,
    model_spec_ref=model_ref,
    compatible=True,
    compatibility_notes=[
        "All specifications validated",
        "Compatible schema versions",
        "No conflicting constraints"
    ]
)
```

### TrinityManifest

Манифест эксперимента с метаданными Trinity артефактов.

```python
from polisyos.core.contracts.trinity import TrinityManifest

manifest = TrinityManifest(
    manifest_id="exp_001_policy_optimization",
    bundle=trinity_bundle,
    experiment_name="Credit Risk Policy Optimization",
    created_by="alice@company.com",
    created_at="2024-01-15T10:00:00Z",
    notes=[
        "First experiment with new risk model",
        "Focus on fraud detection improvement"
    ]
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

### Работа с Trinity контрактами

```python
def setup_experiment_context(store: FileSystemCAS, trinity_bundle: TrinityBundle) -> dict:
    """Настройка контекста эксперимента на основе Trinity bundle"""

    # Загрузка и валидация всех трех спецификаций
    problem_frame = load_problem_frame(store, trinity_bundle.problem_frame_ref)
    policy_spec = load_policy_spec(store, trinity_bundle.policy_spec_ref)
    model_spec = load_model_spec(store, trinity_bundle.model_spec_ref)

    # Проверка совместимости
    if not trinity_bundle.compatible:
        raise ValueError(f"Incompatible Trinity specs: {trinity_bundle.compatibility_notes}")

    return {
        "problem_frame": problem_frame,
        "policy_spec": policy_spec,
        "model_spec": model_spec,
        "compatibility_verified": True
    }
```

### Создание Trinity bundle для эксперимента

```python
def create_trinity_bundle_for_experiment(
    store: FileSystemCAS,
    problem_frame_id: str,
    policy_spec_id: str,
    model_spec_id: str
) -> TrinityBundle:
    """Создание валидного Trinity bundle"""

    # Создание типизированных ссылок
    problem_ref = ProblemFrameRef.from_artifact_ref(
        ArtifactRef(artifact_id=problem_frame_id, kind="ir.problem_frame", media_type="application/json")
    )
    policy_ref = PolicySpecRef.from_artifact_ref(
        ArtifactRef(artifact_id=policy_spec_id, kind="ir.policy_spec", media_type="application/json")
    )
    model_ref = ModelSpecRef.from_artifact_ref(
        ArtifactRef(artifact_id=model_spec_id, kind="ir.model_spec", media_type="application/json")
    )

    # Валидация совместимости (упрощенная)
    compatible = validate_trinity_compatibility(store, problem_ref, policy_ref, model_ref)

    return TrinityBundle(
        problem_frame_ref=problem_ref,
        policy_spec_ref=policy_ref,
        model_spec_ref=model_ref,
        compatible=compatible,
        compatibility_notes=["Validation completed"] if compatible else ["Compatibility issues found"]
    )
```

### Работа с Scientist контрактами

```python
from polisyos.core.contracts.scientist import FailureCardRef, PolicyIRRef, CritiqueRef
from polisyos.scientist.agent.failure_card import FailureCard

# Создание ссылки на FailureCard
def create_failure_card_ref(card: FailureCard) -> FailureCardRef:
    """Создание типизированной ссылки на FailureCard"""
    return FailureCardRef.from_card(card)

# Создание ссылки на PolicyIR с метаданными
def create_policy_ir_ref(cas_hash: str, version: int, status: str) -> PolicyIRRef:
    """Создание ссылки на PolicyIR артефакт"""
    return PolicyIRRef(
        cas_hash=cas_hash,
        version=version,
        status=status
    )

# Создание ссылки на оценку критика
def create_critique_ref(cas_hash: str, verdict: str, ir_hash: str) -> CritiqueRef:
    """Создание ссылки на артефакт оценки критика"""
    return CritiqueRef(
        cas_hash=cas_hash,
        verdict=verdict,
        ir_ref=ir_hash
    )

# Управление состоянием эксперимента
def track_experiment_state(policy_refs: list[PolicyIRRef], critique_refs: list[CritiqueRef]) -> dict:
    """Отслеживание состояния эксперимента с помощью Scientist контрактов"""

    # Группировка по вердиктам критика
    approved = [ref for ref in critique_refs if ref.verdict == "approve"]
    revisions = [ref for ref in critique_refs if ref.verdict == "revise"]
    rejected = [ref for ref in critique_refs if ref.verdict == "reject"]

    return {
        "total_policies": len(policy_refs),
        "approved": len(approved),
        "pending_revision": len(revisions),
        "rejected": len(rejected),
        "latest_version": max((ref.version for ref in policy_refs), default=0)
    }
```

## Архитектурная роль

### Разделение ответственности

- **Contracts**: Определяют интерфейсы и типы данных для всех модулей (Fabric, Foundry, Scientist, Trinity)
- **Artifacts**: Предоставляют инфраструктуру хранения и CAS для всех артефактов
- **Модули**: Реализуют логику, используя контракты для типобезопасного взаимодействия

### Trinity архитектура

Trinity контракты реализуют паттерн "триединства" для структурирования экспериментов:

- **ProblemFrame**: "Почему" - определение проблемы и требований
- **PolicySpec**: "Что" - спецификация поведения политики
- **ModelSpec**: "Как" - модель мира и механизмы исполнения

Этот подход обеспечивает:
- Структурированное описание экспериментов
- Явное разделение concerns между компонентами
- Возможность независимого развития каждого аспекта
- Удобство анализа и воспроизводимости экспериментов

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

# Scientist координирует эксперименты, используя все типы контрактов
def scientist_experiment_workflow(
    trinity_bundle: TrinityBundle,
    fabric_result: FabricResultRef,
    foundry_metrics: MetricsRef
) -> PolicyIRRef:
    """Полный workflow эксперимента в Scientist"""

    # 1. Использование Trinity bundle для контекста
    context = setup_experiment_context(trinity_bundle)

    # 2. Работа с данными из Fabric
    data_context = integrate_fabric_data(fabric_result)

    # 3. Мониторинг метрик из Foundry
    performance_data = analyze_foundry_metrics(foundry_metrics)

    # 4. Генерация и оценка политик
    policy_ir = generate_policy_ir(context, data_context, performance_data)

    # 5. Создание типизированной ссылки на результат
    policy_ref = PolicyIRRef(
        cas_hash=policy_ir.content_hash,
        version=policy_ir.version,
        status="draft"
    )

    return policy_ref
```

### Работа с Legal контрактами

```python
from polisyos.core.contracts.legal import NormPack, NormRule, RuleType, RuleBackend
from polisyos.scientist.governance.legal.backends.base import ValidationResult

# Создание пакета норм для валидации политики
def create_policy_validation_pack() -> NormPack:
    """Создание пакета норм для валидации экономической политики."""

    return NormPack(
        schema_version="1.0",
        norms=[
            NormRule(
                rule_id="budget_balance",
                rule_type=RuleType.CONSTRAINT,
                description="Бюджетный баланс должен быть положительным",
                expression="budget_balance >= 0",
                severity="critical"
            ),
            NormRule(
                rule_id="inflation_control",
                rule_type=RuleType.ECONOMIC,
                description="Инфляция не должна превышать 5%",
                expression="inflation_rate <= 0.05",
                severity="high"
            ),
            NormRule(
                rule_id="privacy_retention",
                rule_type=RuleType.PRIVACY,
                description="Данные о доходах хранятся не более 7 лет",
                expression="income_data_retention_years <= 7",
                severity="medium"
            )
        ]
    )

# Использование RuleBackend для валидации
class EconomicRuleBackend(RuleBackend):
    """Backend для экономических правил валидации."""

    def validate_rule(self, rule: NormRule, context: dict) -> ValidationResult:
        """Валидация экономического правила."""

        try:
            # Простая интерпретация выражений (в реальности использовать безопасный eval)
            result = self._evaluate_expression(rule.expression, context)

            return ValidationResult(
                rule_id=rule.rule_id,
                passed=result,
                message=f"Rule {rule.rule_id}: {'passed' if result else 'failed'}",
                details={"expression": rule.expression, "context": context}
            )
        except Exception as e:
            return ValidationResult(
                rule_id=rule.rule_id,
                passed=False,
                message=f"Validation error: {str(e)}",
                details={"error": str(e)}
            )

    def _evaluate_expression(self, expression: str, context: dict) -> bool:
        """Безопасная оценка выражения (упрощенная версия)."""
        # В реальности использовать restricted eval или AST
        return True  # Placeholder

# Интеграция с governance
def validate_policy_with_legal_rules(
    policy_results: dict,
    norm_pack: NormPack,
    backend: RuleBackend
) -> dict:
    """Валидация результатов политики с использованием legal контрактов."""

    validation_results = []

    for norm in norm_pack.norms:
        result = backend.validate_rule(norm, policy_results)
        validation_results.append(result)

    # Анализ результатов
    passed = sum(1 for r in validation_results if r.passed)
    total = len(validation_results)

    return {
        "validation_results": validation_results,
        "passed_rules": passed,
        "total_rules": total,
        "compliance_rate": passed / total if total > 0 else 0,
        "critical_failures": [
            r for r in validation_results
            if not r.passed and norm_pack.get_rule(r.rule_id).severity == "critical"
        ]
    }
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