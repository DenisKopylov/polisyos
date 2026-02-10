# Governance Layer: Управление качеством и безопасностью

Многоуровневый контроль качества, безопасности и соответствия требованиям. Governance обеспечивает validation pipeline с preflight/postflight checks, модульными passes и human oversight.

## Структура

```
governance/                        17 .py файлов
├── preflight.py                   # Preflight validation → (state, GateRequest?)
├── postflight.py                  # Postflight validation → (state, GateDecision?)
├── pipeline.py                    # Orchestrator: запуск passes с short-circuit на BLOCKER
├── profiles.py                    # fast / mvp / strict — наборы проверок
├── telemetry.py                   # ValidationTrace, PassSpan для мониторинга
├── report.py                      # Compliance reports
│
├── passes/                        # Модульные валидаторы
│   ├── base.py                    # ValidatorPass, PassContext, ComplianceIssue
│   ├── budget_pass.py             # Compute / evidence / legitimacy / complexity budgets
│   ├── safety_pass.py             # Запрещённые механизмы и селекторы
│   ├── privacy_pass.py            # PII tiers, access control
│   ├── schema_pass.py             # IR validation (TrinityBundle schema)
│   ├── legal_pass.py              # Юридическая compliance (см. Legal Compliance ниже)
│   ├── quality_gate_pass.py       # Качество данных (интеграция с Fabric quality indicators)
│   ├── confidence_pass.py         # Валидация уровней доверия
│   └── equity_pass.py             # Distributional impact analysis
│
└── legal/                         # Legal compliance backends
    ├── ast_policy.py              # Policy AST representation
    └── backends/
        ├── base.py                # RuleBackend protocol
        ├── expr_ast.py            # AST-based safe expression evaluation
        └── stub.py                # Stub для тестирования и development
```

## Validation Pipeline

Pipeline запускает модульные passes последовательно, short-circuit при первом BLOCKER issue. Каждый pass получает `PassContext` (IR, state, profile, run_id) и возвращает список `ComplianceIssue`.

### Профили валидации

| Профиль | Passes | Назначение |
|---------|--------|-----------|
| `fast` | schema | Быстрая итерация, минимальные проверки |
| `mvp` | schema, budget, safety | Стандартная разработка |
| `strict` | все (включая legal, privacy, equity, quality gate) | Production и compliance |

### Preflight / Postflight

- **Preflight** (`preflight.py`): валидация до выполнения эксперимента. Возвращает `GateRequest` если требуется human approval.
- **Postflight** (`postflight.py`): валидация после выполнения. Возвращает `GateDecision` с финальным вердиктом.

## Validation Passes

| Pass | Что проверяет | Severity |
|------|--------------|----------|
| `budget_pass` | Compute / evidence / legitimacy / complexity бюджеты | BLOCKER при превышении |
| `safety_pass` | Запрещённые mechanisms и selectors в policy IR | BLOCKER |
| `privacy_pass` | PII tier controls, data access permissions | BLOCKER / WARNING |
| `schema_pass` | Структурная валидация TrinityBundle | BLOCKER |
| `legal_pass` | Соответствие юридическим нормам (NormPack) | BLOCKER / WARNING |
| `quality_gate_pass` | Качество данных: missingness, staleness, coverage, outliers | BLOCKER / WARNING |
| `confidence_pass` | Уровни доверия результатов | WARNING |
| `equity_pass` | Distributional impact, Gini, cohort analysis | WARNING / INFO |

## Legal Compliance

Подсистема `legal/` реализует pluggable backends для оценки соответствия юридическим нормам:

- **RuleBackend** (`backends/base.py`) — protocol: `evaluate(norm_pack, context) → List[ComplianceIssue]`. Требования: idempotent, stateless, thread-safe.
- **ExprASTBackend** (`backends/expr_ast.py`) — AST-based evaluation для expression-based норм. Безопасный parsing без code injection.
- **StubBackend** (`backends/stub.py`) — возвращает INFO для всех норм. Используется в тестах и development.

Типы норм: `OBLIGATION` (обязательства), `PROHIBITION` (запреты), `PERMISSION` (разрешения).

LegalPass интегрируется в pipeline через конфигурацию backend:

```python
from polisyos.core.governance.passes.legal_pass import LegalPass
from polisyos.core.governance.legal.backends.stub import StubBackend

legal_pass = LegalPass(backend=StubBackend())
```

## API

```python
from polisyos.scientist.governance.preflight import preflight_checks
from polisyos.scientist.governance.postflight import postflight_checks
from polisyos.scientist.governance.pipeline import run_validation_pipeline

# Preflight
state, gate_request = preflight_checks(experiment_state)

# Полный pipeline
issues = run_validation_pipeline(state, profile="strict")

# Postflight
state, gate_decision = postflight_checks(experiment_state)
```

## Связи

- **kernel** — GateRequest/GateDecision для human gates
- **IR** — TrinityBundle для schema validation, NormPack для legal checks
- **Fabric** — quality indicators для quality_gate_pass
- **engine** — governance nodes вызывают pipeline в рамках workflow
- **lex** — использует PassContext, LegalPass, SafetyPass для norm impact analysis
