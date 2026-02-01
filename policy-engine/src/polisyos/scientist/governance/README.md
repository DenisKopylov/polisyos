# Governance Layer: Управление качеством и безопасностью

**Многоуровневый контроль качества, безопасности и соответствия требованиям**

Governance Layer обеспечивает многоуровневый контроль качества экспериментов с политиками, включая pre-flight и post-flight проверки, safety validation и human oversight.

## Обзор

Папка `governance/` содержит компоненты для контроля качества и безопасности экспериментов. Реализует паттерн "gates" для human oversight и автоматических проверок compliance.

## Архитектура

```
governance/
├── __init__.py           # Экспорт основных компонентов
├── preflight.py         # Preflight validation pipeline
├── postflight.py        # Postflight validation pipeline (GateDecision)
├── pipeline.py          # Orchestrator for validation passes с short-circuit логикой
├── profiles.py          # ValidationProfile presets (fast/mvp/strict)
├── telemetry.py         # ValidationTrace/PassSpan для мониторинга производительности
├── legal/               # Legal compliance validation backends
│   ├── __init__.py
│   ├── ast_policy.py    # AST-based policy structures для legal validation
│   ├── README.md        # Документация по legal validation
│   └── backends/        # Pluggable rule evaluation backends
│       ├── __init__.py
│       ├── base.py      # RuleBackend protocol contract
│       ├── stub.py      # Stub implementation для тестирования
│       └── expr_ast.py  # AST-based backend для safe expression evaluation
└── passes/              # Модульные проверки
    ├── __init__.py
    ├── base.py          # ValidatorPass, PassContext, ComplianceIssue базовые классы
    ├── budget_pass.py   # Контроль бюджетов (compute, evidence, legitimacy, complexity)
    ├── privacy_pass.py  # Контроль приватности (PII tiers, access control)
    ├── safety_pass.py   # Проверка безопасности механизмов и селекторов
    ├── schema_pass.py   # Валидация структуры IR и PolicySurfaceIR compliance
    ├── legal_pass.py    # Legal compliance validation против норм
    └── quality_gate_pass.py # Data quality validation перед симуляцией
```

## Компоненты

### 🚦 Preflight Checks (preflight.py)

Предварительные проверки безопасности перед запуском экспериментов:

#### preflight_checks()
Основная функция pre-flight governance:
```python
def preflight_checks(
    state: dict,
    profile: ValidationProfile | None = None,
) -> tuple[dict, GateRequest | None]:
    """
    Запускает ValidationPipeline и прикрепляет validation_trace к state.

    Returns:
        tuple: (updated_state, gate_request)
        - gate_request: None если проверка прошла
        - gate_request: GateRequest если найдены blocker-issues
    """
```

### 🛑 Postflight Checks (postflight.py)

Пост-запусковые проверки результатов экспериментов:

#### postflight_checks()
```python
def postflight_checks(
    state: dict,
    profile: ValidationProfile | None = None,
) -> tuple[dict, GateDecision | None]:
    """
    Повторно валидирует state через ValidationPipeline и возвращает GateDecision
    при наличии blocker-issues.
    """
```

### 🔁 Validation Pipeline (pipeline.py)

- `ValidationPipeline` упорядочивает и оркестрирует выполнение validation passes с оптимизацией по стоимости
- **Short-circuit логика**: Останавливает выполнение при обнаружении blocker-issues для экономии ресурсов
- **Параллельное выполнение**: Passes без зависимостей выполняются параллельно
- **Telemetry интеграция**: Каждый pass создает `PassSpan` с метриками производительности
- **Конфигурируемые профили**: Разные наборы passes для различных сценариев (fast/mvp/strict)

#### ValidationTrace (telemetry.py)
- `ValidationTrace` фиксирует полную историю выполнения pipeline с timing и метриками
- `PassSpan` для каждого individual pass с CPU/memory usage, duration, status
- Сериализуется в `validation_trace` для аудита и debugging
- Интеграция с основным audit trail системы

### 📊 Validation Profiles (profiles.py)

`ValidationProfile` определяет набор активных passes, их конфигурацию и политику short-circuit:

#### Предопределенные профили:

- **`fast`**: Минимальный набор для быстрой валидации
  - schema_pass (Pydantic validation)
  - privacy_pass (PII checks)
  - budget_pass (budget validation)
  - Short-circuit: enabled

- **`mvp`**: Сбалансированный набор для большинства сценариев
  - schema_pass + safety_pass + privacy_pass + budget_pass
  - Short-circuit: enabled
  - Подходит для development и production

- **`strict`**: Полный набор проверок без оптимизаций
  - Все доступные passes включая Quality Gate Pass
  - Short-circuit: disabled
  - Максимальная безопасность, compliance и качество данных

#### Кастомные профили:
Возможно создание custom профилей с специфическими passes и thresholds для особых требований.

### ⚖️ Legal Pass (legal_pass.py)

Проверка соответствия политик юридическим нормам с поддержкой pluggable backends:

#### LegalPass
```python
class LegalPass(ValidatorPass):
    """
    Validates policy against legal norms.

    Default behavior: Only runs in STRICT profile.
    Can be force-enabled via constructor for testing.

    Delegates actual rule evaluation to injected RuleBackend.
    """
```

**Ключевые особенности:**
- **Profile-aware**: Запускается только в `STRICT` профиле по умолчанию
- **Force-enable**: Можно принудительно включить через конструктор
- **Backend delegation**: Делегирует проверку норм инжектированному `RuleBackend`
- **NormPack integration**: Работает с `NormPack` структурами из IR layer

#### Legal Validation Backends (legal/backends/)

Модульная система backends для оценки юридических норм:

##### RuleBackend Protocol (base.py)
```python
@runtime_checkable
class RuleBackend(Protocol):
    @property
    def backend_id(self) -> str: ...

    def evaluate(
        self,
        norm_pack: "NormPack",
        context: dict,
    ) -> List[ComplianceIssue]: ...
```

##### StubBackend (stub.py)
Базовая реализация для тестирования:
- Возвращает INFO-level "not implemented" issues для всех норм
- Позволяет тестировать LegalPass интеграцию без rule engine
- Указывает на будущие реализации (AST, LLM backends)

##### ExprASTBackend (expr_ast.py)
Продвинутая реализация на базе AST для безопасной оценки норм:
- **Safe evaluation**: AST parsing предотвращает code injection
- **Expression support**: Поддержка математических и логических выражений
- **Policy introspection**: Доступ к параметрам PolicySurfaceIR
- **Error recovery**: Graceful handling evaluation errors

##### ExprASTBackend (expr_ast.py)
Продвинутая реализация на базе AST для безопасной оценки норм:
- **Safe evaluation**: AST parsing предотвращает code injection
- **Expression support**: Поддержка математических и логических выражений
- **Policy introspection**: Доступ к параметрам PolicySurfaceIR
- **Error recovery**: Graceful handling evaluation errors

##### AST Policy Structures (ast_policy.py)
Новые структуры политик для legal validation:
- Расширенные AST узлы для legal evaluation
- Type-safe структуры для policy introspection
- Интеграция с ExprASTBackend
- Поддержка expression-based норм с безопасной оценкой

##### Будущие backends:
- **LLM Backend**: Claude/GPT-based evaluation для комплексных текстовых норм

### 📊 Quality Gate Pass (quality_gate_pass.py)

Проверка качества данных перед запуском симуляции с интеграцией Fabric quality assessment:

#### QualityGatePass
```python
class QualityGatePass(ValidatorPass):
    """
    Validates data quality before simulation execution.

    Behavior by profile:
    - FAST: Skip entirely (not in pass_ids)
    - MVP: Skip entirely (not in pass_ids)
    - STRICT: Run and block on POOR or UNUSABLE quality
    """

    def __init__(
        self,
        *,
        force_run: bool = False,
        critical_metrics: list[str] | None = None,
    ) -> None:
        self._force_run = force_run
        self._critical_metrics = critical_metrics
```

**Ключевые особенности:**
- **Profile-aware**: Запускается только в `STRICT` профиле по умолчанию (можно принудительно включить)
- **Fabric integration**: Использует `QualityIndicators`, `QualityLevel`, `QualityThresholds` из Fabric layer
- **Data Fitness Reports**: Создает `DataFitnessReport` с human-readable summary и failure reasons
- **Evidence Bundle support**: Автоматически извлекает метрики из evidence bundles или вычисляет их on-demand
- **Critical metrics**: Возможность указать список критически важных метрик для дополнительной проверки
- **Multi-source data**: Поддержка данных из evidence bundles, state refs и catalog registry

#### Data Quality Components (Fabric Integration)

**QualityIndicators**: Объективные метрики качества данных
```python
@dataclass
class QualityIndicators:
    metric_id: str
    missingness: float        # Доля пропущенных значений (0.0-1.0)
    staleness_days: int       # Дни с момента последнего обновления
    coverage: float          # Покрытие ожидаемого диапазона (0.0-1.0)
    row_count: int           # Количество строк
    schema_drift: bool       # Изменения в схеме данных
    outlier_ratio: float     # Доля выбросов
    computed_at: datetime    # Время вычисления
```

**QualityLevel**: Классификация уровня качества
```python
class QualityLevel(Enum):
    EXCELLENT = "excellent"   # Отличное качество
    GOOD = "good"            # Хорошее качество
    ACCEPTABLE = "acceptable" # Приемлемое качество
    POOR = "poor"            # Плохое качество
    UNUSABLE = "unusable"    # Непригодное качество
```

**QualityThresholds**: Конфигурируемые пороги для разных профилей
```python
@dataclass(frozen=True)
class QualityThresholds:
    missingness_excellent: float = 0.01    # <1% пропусков = excellent
    missingness_good: float = 0.05         # <5% пропусков = good
    staleness_excellent: int = 7           # <7 дней = excellent
    coverage_excellent: float = 0.99       # >99% покрытия = excellent
    min_row_count: int = 10                # Минимум 10 строк

    @classmethod
    def for_profile(cls, profile_level: str) -> "QualityThresholds":
        """Возвращает thresholds для профиля (FAST/MVP/STRICT)"""
```

#### DataFitnessReport: Человеко-читаемые отчеты

```python
@dataclass
class DataFitnessReport:
    run_id: str
    profile: str = "mvp"
    metrics: List[MetricFitness] = field(default_factory=list)
    overall_passed: bool = True

    def add_metric(self, fitness: MetricFitness) -> None:
        """Добавить оценку метрики"""

    def generate_summary(self) -> str:
        """Сгенерировать ASCII summary"""

    def generate_markdown_summary(self) -> str:
        """Сгенерировать Markdown summary для документации"""
```

#### MetricFitness: Оценка отдельных метрик

```python
@dataclass
class MetricFitness:
    metric_id: str
    indicators: QualityIndicators
    level: QualityLevel
    fail_reasons: List[str] = field(default_factory=list)
    profile_used: str = "mvp"

    @property
    def passed(self) -> bool:
        """True если уровень качества приемлемый"""
        return self.level.is_passing()
```

## Архитектура Governance

### Многоуровневый контроль с модульной архитектурой

```
┌─────────────────────────────────────┐
│         User Request                │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│      PREFLIGHT GOVERNANCE           │◄── Kernel Human Gates
│                                     │
│  ┌─────────────────────────────────┐ │
│  │   Validation Pipeline          │ │
│  │   ┌─────────────────────────────┐ │ │
│  │   │ Schema Pass                │ │ │
│  │   │ Safety Pass                │ │ │
│  │   │ Privacy Pass               │ │ │
│  │   │ Budget Pass                │ │ │
│  │   │ Quality Gate Pass          │ │ │
│  │   └─────────────────────────────┘ │ │
│  │                                 │ │
│  │   • Modular Design             │ │
│  │   • Short-circuit Logic        │ │
│  │   • Parallel Execution         │ │
│  │   • Telemetry & Tracing        │ │
│  └─────────────────────────────────┘ │
│                                     │
│  ┌─────────────────────────────────┐ │
│  │   Risk Assessment              │ │
│  │   • Impact Magnitude           │ │
│  │   • Uncertainty Bounds         │ │
│  │   • Systemic Risk              │ │
│  └─────────────────────────────────┘ │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│      EXPERIMENT EXECUTION           │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│     POSTFLIGHT GOVERNANCE          │
│                                     │
│  ┌─────────────────────────────────┐ │
│  │   Result Validation            │ │
│  │   • Statistical Significance   │ │
│  │   • Reproducibility Checks     │ │
│  │   • Evidence Quality           │ │
│  └─────────────────────────────────┘ │
│                                     │
│  ┌─────────────────────────────────┐ │
│  │   Governor Decision            │ │
│  │   • Policy Approval/Rejection  │ │
│  │   • Confidence Intervals       │ │
│  │   • Risk Assessment            │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Gate System

Интеграция с Kernel human gate system:

```python
from polisyos.scientist.kernel.human_gate import GateRequest, GateDecision

# Preflight может инициировать human gate
gate_request = GateRequest(
    run_id="exp_001",
    reason="Политика превышает бюджетный дефицит",
    details={"deficit": -1500.0, "threshold": -1000.0}
)

# Postflight может дать финальное решение
gate_decision = GateDecision(
    approved=False,
    actor="admin@policy.org",
    reason_codes=["budget_exceeded"],
    notes="Уменьшите субсидии на 20%"
)
```

## API Использование

### Preflight Integration

```python
from polisyos.scientist.governance.preflight import preflight_checks
from polisyos.scientist.governance.profiles import ValidationProfile, get_profile
from polisyos.scientist.orchestrator.state import ExperimentState

def preflight_node(state: ExperimentState) -> ExperimentState:
    """Узел workflow для preflight governance с выбором профиля."""

    # Выбор профиля валидации (из state или по умолчанию)
    profile_name = state.get("validation_profile", "mvp")
    profile = get_profile(profile_name)

    # Выполнение проверок с выбранным профилем
    updated_state, gate_request = preflight_checks(state, profile=profile)

    if gate_request:
        # Требуется human approval
        return {
            **updated_state,
            "gate_request": gate_request,
            "require_human_gate": True,
            "phase": "PREFLIGHT_GOV",  # Ожидание решения
            "validation_trace": updated_state.get("validation_trace")  # Telemetry data
        }

    # Проверки пройдены, продолжаем
    return {
        **updated_state,
        "preflight_approved": True,
        "validation_profile_used": profile_name
    }
```

### Postflight Integration

```python
from polisyos.scientist.governance.postflight import postflight_checks

def postflight_node(state: ExperimentState) -> ExperimentState:
    """Узел workflow для postflight governance."""

    # Выполнение проверок результатов
    updated_state, gate_decision = postflight_checks(state)

    if gate_decision and not gate_decision.approved:
        # Результаты не прошли проверки
        return {
            **updated_state,
            "gate_decision": gate_decision,
            "governor_verdict": "REJECT",
            "rejection_reasons": gate_decision.reason_codes
        }

    # Результаты одобрены
    return {
        **updated_state,
        "postflight_approved": True,
        "governor_verdict": "APPROVE"
    }
```

### Работа с Validation Profiles

```python
from polisyos.scientist.governance.profiles import get_profile, ValidationProfile
from polisyos.scientist.governance.pipeline import ValidationPipeline

# Использование предопределенных профилей
fast_profile = get_profile("fast")      # Быстрая валидация
mvp_profile = get_profile("mvp")        # Сбалансированная
strict_profile = get_profile("strict")  # Максимальная безопасность

# Кастомный профиль
custom_profile = ValidationProfile(
    name="custom",
    passes=["schema_pass", "budget_pass"],  # Только необходимые passes
    short_circuit=True,
    timeout_seconds=30.0
)

# Применение профиля
pipeline = ValidationPipeline(profile=custom_profile)
result = pipeline.run(state)

print(f"Profile: {result.profile_name}")
print(f"Duration: {result.total_duration}s")
print(f"Passed: {len(result.passed_passes)}/{len(result.total_passes)}")
```

### Работа с Legal Pass

```python
from polisyos.scientist.governance.passes.legal_pass import LegalPass
from polisyos.scientist.governance.legal.backends.stub import StubBackend
from polisyos.ir.norm_pack import NormPack, NormRule, NormRef, RuleType

# Создание LegalPass с кастомным backend
legal_pass = LegalPass(backend=StubBackend())

# Или принудительное включение для тестирования
legal_pass_force = LegalPass(backend=StubBackend(), enabled=True)

# Создание NormPack для тестирования
norm_pack = NormPack(
    pack_id="gdpr_test_pack",
    jurisdiction="EU",
    effective_date="2024-01-01",
    norms=[
        NormRule(
            norm_id="GDPR-5-1-a",
            provision_refs=[
                NormRef(
                    provision_id="Art.5.1.a",
                    source_document="EU/GDPR/2016"
                )
            ],
            rule_type=RuleType.OBLIGATION,
            description="Data must be processed lawfully",
            backend_refs=["ast", "llm"]
        )
    ]
)

# Использование в state
state_with_norms = {
    "run_id": "test_legal",
    "norm_pack": norm_pack,
    "policy_ir": valid_policy_ir
}

# LegalPass автоматически найдет norm_pack в state
issues = legal_pass.validate(PassContext(
    ir=valid_policy_ir,
    state=state_with_norms,
    profile=get_profile("strict"),  # Legal pass работает только в strict
    run_id="test_legal"
))

# StubBackend вернет INFO issues для каждой нормы
print(f"Legal validation issues: {len(issues)}")
for issue in issues:
    print(f"- {issue.code}: {issue.message}")
```

### Работа с Quality Gate Pass

```python
from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass
from polisyos.fabric.quality import QualityIndicators, QualityLevel, QualityThresholds
from polisyos.fabric.fitness_report import DataFitnessReport, MetricFitness

# Создание QualityGatePass с кастомными настройками
quality_pass = QualityGatePass(
    force_run=True,  # Принудительно включить (иначе только в STRICT профиле)
    critical_metrics=["gdp", "unemployment"]  # Критически важные метрики
)

# Создание тестовых quality indicators
indicators = QualityIndicators(
    metric_id="gdp_data",
    missingness=0.02,        # 2% пропусков
    staleness_days=3,        # 3 дня с обновления
    coverage=0.95,          # 95% покрытия
    row_count=1000,         # 1000 строк
    schema_drift=False,     # Схема не изменилась
    outlier_ratio=0.03      # 3% выбросов
)

# Создание mock evidence bundle
evidence_bundle = {
    "sources": [{"artifact_id": "gdp_data"}],
    "quality_indicators": {
        "gdp_data": indicators.to_dict()
    }
}

# Тестовое состояние с evidence bundle
state_with_data = {
    "run_id": "test_quality",
    "evidence_bundle": evidence_bundle,
    "policy_ir": valid_policy_ir
}

# Запуск quality gate validation
issues = quality_pass.validate(PassContext(
    ir=valid_policy_ir,
    state=state_with_data,
    profile=get_profile("strict"),  # Quality pass работает только в strict
    run_id="test_quality"
))

# Проверка результатов
if issues:
    print(f"Quality issues found: {len(issues)}")
    for issue in issues:
        print(f"- {issue.code}: {issue.message}")
        if issue.suggestion:
            print(f"  Suggestion: {issue.suggestion}")
else:
    print("✅ All quality checks passed")

# Получение fitness report из state
fitness_report = state_with_data.get("data_fitness_report")
if fitness_report:
    print(f"Fitness report: {fitness_report.overall_passed}")
    print(f"Summary:\n{fitness_report.generate_summary()}")
```

### Работа с Quality Components

```python
from polisyos.fabric.quality import QualityIndicators, QualityLevel, QualityThresholds, compute_quality_indicators
import pandas as pd

# Вычисление quality indicators из DataFrame
df = pd.DataFrame({
    "gdp": [1000, 1050, 1100, None, 1200],  # Одна строка с пропуском
    "year": [2020, 2021, 2022, 2023, 2024]
})

indicators = compute_quality_indicators(
    df=df,
    metric_id="gdp_metric",
    last_updated=pd.Timestamp("2024-01-15"),  # 10 дней назад
    expected_row_count=5
)

print(f"Missingness: {indicators.missingness:.1%}")
print(f"Staleness: {indicators.staleness_days} days")
print(f"Coverage: {indicators.coverage:.1%}")

# Определение уровня качества
thresholds = QualityThresholds.for_profile("strict")
level = indicators.overall_level(thresholds)
print(f"Quality level: {level.value}")

# Получение причин неудач
if not level.is_passing():
    reasons = indicators.get_failure_reasons(thresholds)
    print("Failure reasons:")
    for reason in reasons:
        print(f"- {reason}")
```

### Кастомные проверки

```python
from polisyos.scientist.governance.passes.base import ValidatorPass, ComplianceIssue
from polisyos.scientist.governance.passes.base import IssueSeverity

class CustomEconomicPass(ValidatorPass):
    """Кастомная проверка экономических показателей."""

    def validate(self, context) -> list[ComplianceIssue]:
        issues = []

        # Проверка бюджетного дефицита
        deficit = context.state.get("simulation_results", {}).get("budget_deficit", 0)
        if deficit < -1000.0:
            issues.append(ComplianceIssue(
                pass_name=self.name,
                message="Excessive budget deficit detected",
                severity=IssueSeverity.BLOCKER,
                details={"deficit": deficit, "threshold": -1000.0}
            ))

        # Проверка воздействия на бедность
        poverty_change = context.state.get("simulation_results", {}).get("poverty_rate_change", 0)
        if poverty_change > 0.05:  # >5% increase
            issues.append(ComplianceIssue(
                pass_name=self.name,
                message="Significant increase in poverty rate",
                severity=IssueSeverity.WARNING,
                details={"change": poverty_change}
            ))

        return issues

# Регистрация кастомного pass
from polisyos.scientist.governance.pipeline import ValidationPipeline
pipeline.register_pass(CustomEconomicPass())
```

## Примеры реализации

### Safety Validation

```python
def validate_policy_safety(ir: PolicySurfaceIR) -> list[str]:
    """Валидация безопасности политики."""

    issues = []

    # Проверка запрещенных механизмов
    forbidden_mechanisms = ["wealth_confiscation", "population_control"]
    for intervention in ir.semantic.interventions:
        if intervention.kind in forbidden_mechanisms:
            issues.append(f"Forbidden mechanism: {intervention.kind}")

    # Проверка экстремальных значений
    for intervention in ir.semantic.interventions:
        if "rate" in intervention.params:
            rate = float(intervention.params["rate"])
            if not 0 <= rate <= 1:
                issues.append(f"Invalid rate value: {rate} (must be 0-1)")

    return issues
```

### Risk Assessment

```python
def assess_policy_risk(results: dict) -> dict:
    """Оценка рисков политики."""

    risk_score = 0
    risk_factors = []

    # Фискальный риск
    deficit = results.get("budget_deficit", 0)
    if deficit < -500:
        risk_score += 2
        risk_factors.append("high_fiscal_deficit")

    # Социальный риск
    unemployment_change = results.get("unemployment_change", 0)
    if unemployment_change > 0.03:  # >3% increase
        risk_score += 1
        risk_factors.append("unemployment_increase")

    # Макроэкономический риск
    gdp_change = results.get("gdp_change", 0)
    if gdp_change < -0.02:  # >2% GDP drop
        risk_score += 2
        risk_factors.append("gdp_contraction")

    return {
        "risk_score": risk_score,
        "risk_level": "high" if risk_score >= 3 else "medium" if risk_score >= 1 else "low",
        "risk_factors": risk_factors
    }
```

### Statistical Validation

```python
def validate_statistical_significance(results: dict) -> dict:
    """Проверка статистической значимости результатов."""

    validation = {
        "significant_effects": [],
        "insignificant_effects": [],
        "confidence_intervals": {},
        "recommendations": []
    }

    # Проверка confidence intervals
    for metric, value in results.items():
        if isinstance(value, dict) and "ci_lower" in value:
            ci_width = value["ci_upper"] - value["ci_lower"]
            validation["confidence_intervals"][metric] = {
                "width": ci_width,
                "significant": abs(value["mean"]) > ci_width  # Rough significance test
            }

            if abs(value["mean"]) > ci_width:
                validation["significant_effects"].append(metric)
            else:
                validation["insignificant_effects"].append(metric)

    return validation
```

## Интеграция с Kernel

### Human Gate Workflow

```python
# 1. Preflight инициирует gate request
state, gate_request = preflight_checks(state)
if gate_request:
    state["gate_request"] = gate_request
    state["require_human_gate"] = True
    # Workflow переходит в ожидание

# 2. Human предоставляет gate decision
gate_decision = GateDecision(approved=True, actor="admin@example.com")
state["gate_decision"] = gate_decision

# 3. Postflight validates decision
final_state, final_decision = postflight_checks(state)
if final_decision:
    state["final_governance_decision"] = final_decision
```

### Governor Integration

```python
from polisyos.scientist.orchestrator.flow_nodes import governor_node

def governor_node(state: ExperimentState) -> ExperimentState:
    """Governor node с интеграцией governance."""

    # Выполнение postflight проверок
    updated_state, gate_decision = postflight_checks(state)

    # Формирование governor feedback
    feedback = GovernorFeedback(
        verdict="APPROVE" if gate_decision is None or gate_decision.approved else "REJECT",
        issues=extract_issues_from_decision(gate_decision) if gate_decision else []
    )

    return {**updated_state, "feedback": feedback}
```

## Тестирование

### Unit тесты

```bash
# Тестирование governance layer
pytest tests/scientist/test_governance_*.py -v

# Preflight/postflight checks
pytest tests/scientist/test_governance_preflight.py -v
pytest tests/scientist/test_governance_postflight.py -v

# Validation pipeline и passes
pytest tests/scientist/test_governance_pipeline.py -v
pytest tests/scientist/test_governance_passes.py -v
pytest tests/scientist/test_governance_legal_pass.py -v  # Legal compliance validation

# Profiles и telemetry
pytest tests/scientist/test_governance_profiles.py -v
pytest tests/scientist/test_governance_telemetry.py -v
```

### Mock тестирование

```python
def test_preflight_with_gate_request():
    """Тестирование preflight с gate request."""

    state = {
        "run_id": "test_exp",
        "simulation_results": {"budget_deficit": -1500.0}
    }

    updated_state, gate_request = preflight_checks(state)

    assert gate_request is not None
    assert "budget deficit" in gate_request.reason.lower()
    assert gate_request.details["deficit"] == -1500.0
```

### Integration тесты

```python
from polisyos.scientist.governance.pipeline import ValidationPipeline
from polisyos.scientist.governance.profiles import get_profile

def test_validation_pipeline_integration():
    """Тестирование полной validation pipeline."""

    # Создание тестового состояния
    state = {
        "run_id": "test_pipeline",
        "ir": create_test_policy_ir(),
        "budget": {"max_llm_calls": 5}
    }

    # Выполнение pipeline с профилем
    profile = get_profile("mvp")
    pipeline = ValidationPipeline(profile=profile)
    result = pipeline.run(state)

    # Проверка результатов
    assert result.total_passes > 0
    assert result.validation_trace is not None
    assert "duration" in result.validation_trace

    # Проверка telemetry
    trace = result.validation_trace
    assert len(trace.pass_spans) == len(result.total_passes)

def test_legal_pass_integration():
    """Тестирование LegalPass интеграции с pipeline."""
    from polisyos.scientist.governance.passes.legal_pass import LegalPass
    from polisyos.ir.norm_pack import NormPack, NormRule, RuleType

    # Создание test norm pack
    norm_pack = NormPack(
        pack_id="test_legal",
        jurisdiction="TEST",
        norms=[
            NormRule(
                norm_id="TEST-1",
                rule_type=RuleType.OBLIGATION,
                description="Test legal requirement"
            )
        ]
    )

    state = {
        "run_id": "test_legal_integration",
        "norm_pack": norm_pack
    }

    # Тестирование в strict профиле
    profile = get_profile("strict")
    pipeline = ValidationPipeline(profile=profile)
    result = pipeline.run(state)

    # Legal pass должен выполниться и вернуть issues от StubBackend
    legal_issues = [span for span in result.validation_trace.pass_spans
                   if span.pass_id == "legal"]
    assert len(legal_issues) == 1
    assert legal_issues[0].issues_count == 1  # Один issue от StubBackend

def test_full_governance_workflow():
    """Тестирование полного governance workflow с pipeline."""

    from polisyos.scientist.governance.preflight import preflight_checks
    from polisyos.scientist.governance.postflight import postflight_checks

    # Имитация workflow
    state = {
        "run_id": "integration_test",
        "ir": create_valid_policy_ir(),
        "budget": {"max_llm_calls": 3}
    }

    # Preflight с pipeline
    state, gate_req = preflight_checks(state, profile=get_profile("fast"))
    if gate_req:
        # Human decision
        state["gate_decision"] = GateDecision(approved=True, actor="admin")

    # Postflight с pipeline
    state, gate_dec = postflight_checks(state, profile=get_profile("fast"))
    if gate_dec:
        assert gate_dec.approved
```

## Расширение

### Кастомные проверки

```python
class CustomGovernanceChecks:
    """Класс для кастомных governance проверок."""

    def __init__(self, config: dict):
        self.config = config

    def preflight_checks(self, state: dict) -> tuple[dict, GateRequest | None]:
        """Кастомные preflight проверки."""
        # Implementation
        pass

    def postflight_checks(self, state: dict) -> tuple[dict, GateDecision | None]:
        """Кастомные postflight проверки."""
        # Implementation
        pass
```

### Configuration-driven governance

```python
class ConfigurableGovernance:
    """Governance с конфигурируемыми правилами."""

    def __init__(self, rules_config: dict):
        self.rules = rules_config

    def check_rule(self, rule_name: str, state: dict) -> bool:
        """Проверка конкретного правила."""
        rule = self.rules.get(rule_name, {})
        threshold = rule.get("threshold")
        metric = rule.get("metric")

        value = state.get("simulation_results", {}).get(metric)
        if value is None:
            return True  # Skip if metric not available

        operator = rule.get("operator", "lt")
        if operator == "lt":
            return value < threshold
        elif operator == "gt":
            return value > threshold
        # Add more operators...
```

### Audit trail integration

```python
def governance_audit_log(state: dict, action: str, details: dict):
    """Логирование governance действий в audit trail."""

    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "phase": state.get("phase"),
        "action": action,
        "run_id": state.get("run_id"),
        "details": details,
        "actor": "governance_system"
    }

    current_audit = state.get("audit_trail", [])
    current_audit.append(audit_entry)

    return {**state, "audit_trail": current_audit}
```

## Связанные компоненты

- **Kernel**: `GateRequest`, `GateDecision`, `human_gate.py`
- **Orchestrator**: `governor_node`, `preflight/postflight nodes`
- **Runtime**: Audit trail и lifecycle management

## Troubleshooting

### Preflight всегда возвращает gate request

**Решение**: Проверить логику в `preflight_checks` - возможно, слишком строгие правила

### Postflight не находит ожидаемые метрики

```
KeyError: 'simulation_results' not found in state
```

**Решение**: Убедиться, что симуляция выполнена до postflight проверок

### Gate decision не применяется

**Решение**: Проверить, что `gate_decision` правильно сохраняется в state

### Governance блокирует валидные эксперименты

**Решение**: Расслабить thresholds в governance правилах или добавить исключения

### Audit trail не обновляется

**Решение**: Убедиться, что governance функции вызывают `append_audit` из orchestrator
