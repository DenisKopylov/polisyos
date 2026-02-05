# Governance Layer: Управление качеством и безопасностью

**Многоуровневый контроль качества, безопасности и соответствия требованиям**

Governance обеспечивает validation pipeline с preflight/postflight checks, modular passes и human oversight.

## Структура

```
governance/
├── preflight.py     # Preflight validation pipeline
├── postflight.py    # Postflight checks и GateDecision
├── pipeline.py      # Orchestrator для validation passes
├── profiles.py      # fast/mvp/strict validation profiles
├── telemetry.py     # Validation telemetry
├── report.py        # Compliance reports
├── legal/           # Legal compliance backends
└── passes/          # Modular validators
    ├── base.py      # ValidatorPass базовый класс
    ├── budget_pass.py # Budget controls
    ├── safety_pass.py # Safety validation
    ├── privacy_pass.py # PII controls
    ├── schema_pass.py # IR validation
    ├── legal_pass.py # Legal compliance
    └── quality_gate_pass.py # Data quality
```

## Ключевые компоненты

- **Preflight/Postflight**: Автоматические проверки перед/после выполнения
- **Validation Passes**: Модульная система проверок (budget, safety, privacy, schema, legal, quality)
- **Legal Compliance**: AST-based backends для safe expression evaluation
- **Profiles**: Конфигурируемые уровни валидации (fast/mvp/strict)
- **Human Gates**: GateRequest/GateDecision для human oversight

## API Использование

```python
from polisyos.scientist.governance.preflight import preflight_checks
from polisyos.scientist.governance.pipeline import run_validation_pipeline

# Preflight проверки
state, gate_request = preflight_checks(experiment_state)

# Validation pipeline
issues = run_validation_pipeline(state, profile="strict")
```

## Связи

- Интегрируется с **engine** для workflow validation
- Использует **IR** для policy structure validation
- Поддерживает **Fabric** для data quality assessment