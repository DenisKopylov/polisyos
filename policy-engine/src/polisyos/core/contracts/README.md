# Contracts (Типизированные контракты)

Типизированные контракты взаимодействия между модулями PolisyOS. Типобезопасность, стандартизация интерфейсов, provenance tracking.

## Архитектура

```
contracts/
├── compiler.py     # Compile/Link отчеты
├── fabric.py       # Fabric контракты (6 типов)
├── foundry.py      # Foundry контракты (15+ типов, patch-based state)
├── lex.py          # Legal контракты, RuleBackend protocol
├── legal.py        # DEPRECATED (shim для lex)
├── scholar.py      # Scholar контракты (ResearchIntent)
├── scientist.py    # Scientist контракты (FailureCardRef, etc.)
└── trinity.py      # Trinity контракты (ProblemFrame, PolicySpec, ModelSpec)
```

## Принципы

- Типизированные ссылки с `Literal` типами для kind/media_type
- Разделение данных и ссылок
- Строгая типизация с `extra="forbid"`

## Compiler Contracts

- **CompileReportRef**: Отчет компиляции политики
- **LinkReportRef**: Отчет линковки программы

```python
from polisyos.core.contracts.compiler import CompileReportRef, LinkReportRef

compile_ref = CompileReportRef(artifact_id=id, kind="compiler.compile_report")
link_ref = LinkReportRef(artifact_id=id, kind="compiler.link_report")
```

## Fabric Contracts

7+ типов контрактов для обработки и агрегации данных.

- **DataViewRequestRef**: Запрос на представление данных
- **QueryPlan & QueryPlanRef**: План запроса с шагами выполнения
- **EvidenceBundle & EvidenceBundleRef**: Пакет доказательств с provenance и quality indicators
- **FabricResult & FabricResultRef**: Результат обработки с метаданными
- **UncertaintyBounds & UncertaintyBoundsRef**: Границы неопределенности
- **WarningsBundle & WarningsRef**: Предупреждения о проблемах
- **DataSnapshot & DataSnapshotRef**: Фиксированный снапшот данных

```python
from polisyos.core.contracts.fabric import QueryPlan, EvidenceBundle, FabricResult

plan = QueryPlan(request_ref=req_ref, steps=[...], trust_policy_id="strict")
evidence = EvidenceBundle(sources=[...], transforms=[...], quality_indicators={...})
result = FabricResult(request_ref=req_ref, plan_ref=plan_ref, data_ref=data_ref)
```

## Foundry Contracts

15+ типов контрактов для симуляции и исполнения политик с patch-based state management, conflict detection, cost modeling и runtime safety.

### Core Contracts
- **ArtifactRef**: Базовая typed-ссылка на CAS артефакт
- **ProgramGraph & ProgramGraphRef**: Граф программы с узлами и операциями
- **LoweredIR & LoweredIRRef**: Пониженное IR для исполнения
- **ExecPlan & ExecPlanRef**: План исполнения с environment tracking
- **AgentPolicyRef**: Обученная политика агента

### State Management
- **StateSnapshot & StateSnapshotRef**: Снапшоты состояния
- **StateDelta & StateDeltaRef**: Patch-based обновления состояния

### Configuration
- **TreasurySeed & TreasurySeedRef**: Сид для deterministic execution
- **ExecConfig & ExecConfigRef**: Конфигурация исполнения

### Monitoring
- **Metrics & MetricsRef**: Метрики исполнения
- **TraceSliceRef**: Срезы трассировки
- **SimulationResult & SimulationResultRef**: Результаты симуляции

### Validation
- **ConstraintReportRef**: Отчеты ограничений
- **CalibrationReportRef**: Отчеты калибровки

### Advanced Runtime
- **Patch-based state management**: PatchOp, UpdateOp, Patch, PatchSet с confidence scoring
- **Conflict detection**: SlotConflict, ConflictReport для compile-time validation
- **Cost modeling**: CostEstimate, CostBudget для resource-aware execution
- **NaN guard**: NaNDiagnostic, NaNGuardReport для numerical stability

```python
from polisyos.core.contracts.foundry import ProgramGraph, ExecPlan, Patch

graph = ProgramGraph(nodes=[...], edges=[...], inputs=["data"], outputs=["result"])
plan = ExecPlan(program_ref=graph_ref, environment_ref=env_ref, determinism_tier="gpu")
patch = Patch(meta=PatchMeta(confidence=0.89), ops=[update_op])
```

## Trinity Contracts

Фундаментальные спецификации: ProblemFrame ("почему"), PolicySpec ("что"), ModelSpec ("как").

- **ProblemFrameRef**: Контекст и требования к политике
- **PolicySpecRef**: Структура и поведение политики
- **ModelSpecRef**: Модель мира и компоненты
- **TrinityBundle & TrinityBundleRef**: Полный bundle спецификаций

```python
from polisyos.core.contracts.trinity import TrinityBundle

bundle = TrinityBundle(
    problem_frame_ref=problem_ref,
    policy_spec_ref=policy_ref,
    model_spec_ref=model_ref
)
```

## Scientist Contracts

Контракты для оркестрации экспериментов и управления жизненным циклом политик.

- **ExperimentStateRef**: Снапшоты экспериментального состояния
- **DecisionPacketRef**: Пакеты решений
- **FailureCardRef**: Карты неудач с метаданными (attempt_number, error_code, can_retry)
- **TrinityIRRef**: TrinityBundle с версиями и статусом
- **CritiqueRef**: Оценки критика
- **TimelineRef**: Таймлайны экспериментов с event_count и duration
- **DecisionCardRef**: Детерминированные сводки результатов (verdict, generated_at)

```python
from polisyos.core.contracts.scientist import FailureCardRef, DecisionCardRef

failure_ref = FailureCardRef(
    artifact_id=id,
    attempt_number=3,
    error_code="VALIDATION_ERROR",
    can_retry=True
)

decision_ref = DecisionCardRef(
    artifact_id=id,
    run_id="exp_001",
    verdict="APPROVE"
)
```

## Lex Contracts

Интерфейсы для compliance-валидации политик и pluggable rule backends.

- **ComplianceIssue**: Проблемы compliance с severity (BLOCKER/CRITICAL/etc.)
- **RuleBackend**: Protocol для pluggable backends валидации
- **LegalContext**: Контекст валидации (trinity bundle, fabric results, jurisdiction)
- **LegalReportRef & ChangeProposalRef**: Отчеты и предложения изменений

```python
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity, RuleBackend

issue = ComplianceIssue(
    pass_id="legal",
    path=["policy", "budget"],
    message="Budget deficit exceeds 5%",
    severity=IssueSeverity.BLOCKER
)

class CustomBackend(RuleBackend):
    @property
    def backend_id(self) -> str:
        return "custom.v1"

    def evaluate(self, norm_pack, context) -> list[ComplianceIssue]:
        return []
```

## Scholar Contracts

ABI-стык для исследовательского обогащения (без реализации).

- **ResearchIntent**: Запросы на исследование (domain, topic, time_window, budgets)
- **KnowledgeBundleRef**: Ссылки на пакеты знаний

```python
from polisyos.core.contracts.scholar import ResearchIntent, TimeWindow

intent = ResearchIntent(
    domain="labor",
    topic="minimum_wage",
    jurisdictions=["US-CA"],
    time_window=TimeWindow(start="2020-01-01", end="2025-12-31"),
    budgets={"max_docs": 200}
)
```

## Производительность

- **Типизация**: Compile-time проверки без runtime overhead
- **Валидация**: Эффективная Pydantic валидация
- **Хранение**: JSON сериализация с оптимизацией
- **Доступ**: Быстрое чтение/запись через CAS

## Лучшие практики

- Используйте типизированные ссылки вместо общего ArtifactRef
- Валидируйте данные при загрузке
- Поддерживайте provenance через входные ссылки
- Версионируйте схемы семантически
- Применяйте advanced Foundry contracts (conflict detection, cost modeling, NaN guard)
