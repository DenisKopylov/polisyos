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
└── passes/
    ├── __init__.py
    ├── base.py          # ValidatorPass, PassContext, ComplianceIssue базовые классы
    ├── budget_pass.py   # Контроль бюджетов (compute, evidence, legitimacy, complexity)
    ├── privacy_pass.py  # Контроль приватности (PII tiers, access control)
    ├── safety_pass.py   # Проверка безопасности механизмов и селекторов
    └── schema_pass.py   # Валидация структуры IR и PolicySurfaceIR compliance
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
  - Все доступные passes
  - Short-circuit: disabled
  - Максимальная безопасность и compliance

#### Кастомные профили:
Возможно создание custom профилей с специфическими passes и thresholds для особых требований.

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
