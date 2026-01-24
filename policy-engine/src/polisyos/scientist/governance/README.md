# Governance Layer: Управление качеством и безопасностью

**Многоуровневый контроль качества, безопасности и соответствия требованиям**

Governance Layer обеспечивает многоуровневый контроль качества экспериментов с политиками, включая pre-flight и post-flight проверки, safety validation и human oversight.

## Обзор

Папка `governance/` содержит компоненты для контроля качества и безопасности экспериментов. Реализует паттерн "gates" для human oversight и автоматических проверок compliance.

## Архитектура

```
governance/
├── __init__.py           # Экспорт основных компонентов
├── preflight.py         # Предварительные проверки безопасности
└── postflight.py        # Пост-запусковые проверки результатов
```

## Компоненты

### 🚦 Preflight Checks (preflight.py)

Предварительные проверки безопасности перед запуском экспериментов:

#### preflight_checks()
Основная функция pre-flight governance:
```python
def preflight_checks(state: dict) -> tuple[dict, GateRequest | None]:
    """
    Предварительные проверки безопасности и валидации.

    Returns:
        tuple: (updated_state, gate_request)
        - gate_request: None если проверки пройдены, GateRequest если требуется human approval
    """
    return state, None  # Placeholder implementation
```

**Текущая реализация**: Placeholder с базовой структурой для будущей интеграции.

### 🛑 Postflight Checks (postflight.py)

Пост-запусковые проверки результатов экспериментов:

#### postflight_checks()
Основная функция post-flight governance:
```python
def postflight_checks(state: dict) -> tuple[dict, GateDecision | None]:
    """
    Пост-запусковые проверки результатов и финальное одобрение.

    Returns:
        tuple: (updated_state, gate_decision)
        - gate_decision: None если проверки пройдены, GateDecision с результатом проверки
    """
    return state, None  # Placeholder implementation
```

**Текущая реализация**: Placeholder с базовой структурой для будущей интеграции.

## Архитектура Governance

### Многоуровневый контроль

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
│  │   Safety Validation            │ │
│  │   • Policy Safety Rules        │ │
│  │   • Budget Compliance          │ │
│  │   • PII/Data Access Control    │ │
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
from polisyos.scientist.orchestrator.state import ExperimentState

def preflight_node(state: ExperimentState) -> ExperimentState:
    """Узел workflow для preflight governance."""

    # Выполнение проверок
    updated_state, gate_request = preflight_checks(state)

    if gate_request:
        # Требуется human approval
        return {
            **updated_state,
            "gate_request": gate_request,
            "require_human_gate": True,
            "phase": "PREFLIGHT_GOV"  # Ожидание решения
        }

    # Проверки пройдены, продолжаем
    return {
        **updated_state,
        "preflight_approved": True
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

### Кастомные проверки

```python
def custom_preflight_checks(state: dict) -> tuple[dict, GateRequest | None]:
    """Кастомные preflight проверки."""

    issues = []

    # Проверка бюджетного дефицита
    simulation_results = state.get("simulation_results", {})
    deficit = simulation_results.get("budget_deficit", 0)

    if deficit < -1000.0:  # Threshold для human approval
        gate_request = GateRequest(
            run_id=state.get("run_id"),
            reason="Excessive budget deficit detected",
            details={"deficit": deficit, "threshold": -1000.0}
        )
        return state, gate_request

    # Проверка потенциального воздействия на бедность
    poverty_rate_change = simulation_results.get("poverty_rate_change", 0)
    if poverty_rate_change > 0.05:  # >5% increase
        issues.append("Significant increase in poverty rate")

    if issues:
        return {**state, "preflight_issues": issues}, None

    return state, None
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

# Preflight checks
pytest tests/scientist/test_governance_preflight.py -v

# Postflight checks
pytest tests/scientist/test_governance_postflight.py -v
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
def test_full_governance_workflow():
    """Тестирование полного governance workflow."""

    # Мокаем governance functions
    def mock_preflight(state):
        return state, GateRequest(run_id="test", reason="mock_reason")

    def mock_postflight(state):
        return state, GateDecision(approved=True, actor="test_user")

    # Имитация workflow
    state = {"run_id": "integration_test"}

    # Preflight
    state, gate_req = mock_preflight(state)
    assert gate_req is not None

    # Human decision
    state["gate_decision"] = GateDecision(approved=True, actor="admin")

    # Postflight
    state, gate_dec = mock_postflight(state)
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