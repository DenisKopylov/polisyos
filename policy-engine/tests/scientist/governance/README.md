# Governance Tests

Валидация governance layer - validation pipeline, legal compliance, Phase 18 security validation, safe expression evaluation.

**Последнее обновление:** Январь 2026 (добавлены Phase 18: Safe Expression Evaluation, AST Policy validation, norm execution security, legal AST backends)
**Уровень:** Governance Layer (Validation & Compliance & Security)
**Зависимости:** Core contracts, IR structures, Legal norms, AST policy, Expression evaluators

## Архитектурный контекст

Governance layer обеспечивает безопасность и compliance политик через validation pipeline, legal compliance checking и Phase 18 security validation. Компоненты валидируют политики на pre/post-flight этапах, обеспечивают legal compliance и предотвращают security vulnerabilities через safe expression evaluation.

## Структура тестов

```
governance/
├── test_legal_pass.py     # LegalPass, RuleBackend, NormPack validation
├── test_norm_execution.py # Phase 18: Safe expression evaluation, AST policy, security validation
└── test_validation_pipeline.py # ValidationPipeline, profiles, compliance issues
```

## Категории тестов

### Validation Pipeline (`test_validation_pipeline.py`)

**Цель:** Валидация validation pipeline orchestrator, compliance issues, validation profiles и pass context.

**Ключевые тесты:**
- **Pipeline Orchestration**: Short-circuit logic при blocker issues, pass ordering по стоимости
- **Compliance Issues**: Создание и валидация issues с severity levels (blocker/warning/error)
- **Validation Profiles**: Fast/mvp/strict profiles с разными наборами passes
- **Pass Context**: Shared state между passes, context management
- **Custom Passes**: Создание и интеграция custom validation passes

**Принципы:**
- **Cost-Based Ordering**: Passes упорядочиваются по computational cost
- **Short-Circuit Logic**: Pipeline останавливается при blocker issues
- **Severity Classification**: Structured severity levels с remediation guidance
- **Profile Configuration**: Configurable validation levels для разных scenarios

### Legal Pass (`test_legal_pass.py`)

**Цель:** Валидация legal validation pass, rule backends, norm pack структур и compliance evaluation.

**Ключевые тесты:**
- **Legal Pass Execution**: Profile-based execution (FAST/MVP/STRICT), backend delegation, force enable
- **Rule Backend Protocol**: StubBackend implementation, protocol conformance, runtime type checking
- **Norm Pack Validation**: Schema validation, JSON/dict roundtrip, rule structure integrity
- **Backend Injection**: Custom backend injection, mock testing, evaluation delegation

**Принципы:**
- **Profile-Based Execution**: LegalPass runs only in STRICT profile by default (configurable)
- **Backend Abstraction**: Pluggable rule evaluation через RuleBackend protocol
- **Norm Pack Contracts**: Structured legal norms с jurisdiction, effective dates, rule types
- **Compliance Issues**: Structured feedback с severity levels и remediation guidance

### Phase 18 Safe Expression Evaluation (`test_norm_execution.py`)

**Цель:** Валидация безопасной оценки выражений, AST policy enforcement, security validation и safe expression evaluators.

**Категории тестирования:**
1. **SECURITY** - Verify forbidden constructs are rejected
2. **POLICY** - Verify ASTPolicy validation rules
3. **EVALUATION** - Verify correct evaluation logic
4. **BACKEND** - Verify ExpressionASTBackend integration
5. **EDGE_CASES** - Division by zero, missing variables, etc.

**Ключевые тесты:**
- **Security Rejection**: Отвержение опасных конструкций (imports, eval, exec, file operations, builtins, class escapes, method calls, globals access, subscript operations, infinite loops)
- **AST Policy Validation**: AST limits enforcement (node count, depth limits), forbidden construct detection, policy configuration
- **Safe Expression Evaluator**: Математическая корректность, variable binding, error handling, type safety, numeric operations
- **Backend Integration**: ExpressionASTBackend integration, norm evaluation, compliance checking, rule execution
- **Edge Cases**: Division by zero handling, missing variables, type mismatches, overflow conditions, complex expressions

**Принципы:**
- **Security First**: Все dangerous constructs отвергаются до evaluation через AST analysis
- **AST Analysis**: Static analysis выражений перед execution для security guarantees
- **Limited Scope**: Только безопасные mathematical operations (arithmetic, comparison, logical) и variable references
- **Error Containment**: Graceful handling ошибок без system compromise или information leakage
- **Type Safety**: Strict type checking и validation для всех operations и variable bindings

## Запуск тестов

```bash
# Все governance тесты
pytest tests/scientist/governance/ -v

# Конкретные компоненты
pytest tests/scientist/governance/test_validation_pipeline.py -v # Validation pipeline
pytest tests/scientist/governance/test_legal_pass.py -v            # Legal validation pass
pytest tests/scientist/governance/test_norm_execution.py -v       # Phase 18 security

# Phase 18 security по категориям
pytest tests/scientist/governance/test_norm_execution.py::TestSecurityRejection -v     # Security validation
pytest tests/scientist/governance/test_norm_execution.py::TestASTPolicy -v            # AST policy rules
pytest tests/scientist/governance/test_norm_execution.py::TestSafeExpressionEvaluator -v # Safe evaluation
pytest tests/scientist/governance/test_norm_execution.py::TestExpressionASTBackend -v  # Backend integration
pytest tests/scientist/governance/test_norm_execution.py::TestEdgeCases -v            # Edge case handling
```

## Связи с другими модулями

### Зависимости Governance Layer

**IR Layer** (`ir/`):
- **Norm Pack Structures**: NormPack, NormRule, NormRef для legal validation
- **Legal Contracts**: Stable exports legal типов через core/contracts/legal.py
- **Policy Surface**: Policy structures для validation и compliance checking

**Core Layer** (`core/`):
- **Contracts**: Legal contracts и validation schemas
- **Artifact Storage**: Persistence validation results и compliance reports
- **Registry System**: Centralized configuration для validation profiles

### Потребители Governance Layer

**Scientist Layer** (`scientist/`):
- **Pre/Post-Flight Validation**: Policy validation перед compilation и после generation
- **Compliance Checking**: Legal compliance verification для generated policies
- **Security Validation**: Phase 18 safe expression evaluation для mathematical norms

**Integration Layer** (`integration/`):
- **End-to-End Validation**: Full pipeline validation с governance checks
- **Workflow Safety**: Governance integration в multi-agent workflows
- **Decision Quality**: Governance feedback в decision packets и cards

### Архитектурные инварианты

- **Закон C**: Governance gates (pre-flight validation перед execution, post-flight review)
- **Закон L**: Legal compliance (policies валидируются против applicable legal norms)
- **Закон S**: Security first (Phase 18: dangerous constructs rejected, safe evaluation guaranteed)
- **Pipeline Ordering**: Validation passes ordered по computational cost и short-circuit на blockers
- **Profile Configuration**: Validation levels (fast/mvp/strict) для разных operational contexts
- **Backend Abstraction**: Pluggable rule evaluation через protocol-based architecture
- **AST Security**: Static analysis guarantees для expression evaluation safety

## Разработка и расширение

### Добавление новых governance тестов

1. **Validation Pipeline**: Тестируйте pass orchestration, short-circuit logic, custom passes
2. **Legal Validation**: Проверяйте backend delegation, norm pack validation, compliance issues
3. **Phase 18 Security**: Тестируйте security rejection, AST policy rules, safe evaluation, edge cases
4. Используйте fixtures для shared state (validation profiles, norm packs, compliance issues)
5. Маркируйте integration тесты с `@pytest.mark.integration`

### Структура governance теста

```python
def test_legal_pass_execution(sample_norm_pack: NormPack) -> None:
    """Тестирование LegalPass execution с custom backend."""
    from polisyos.scientist.governance.passes.legal_pass import LegalPass

    # Setup: create mock backend
    mock_backend = MagicMock()
    mock_backend.evaluate.return_value = [ComplianceIssue(...)]

    legal_pass = LegalPass(backend=mock_backend, enabled=True)
    ctx = PassContext(ir=None, state={"norm_pack": sample_norm_pack}, ...)

    # Execute: run legal validation
    issues = legal_pass.validate(ctx)

    # Verify: backend called and issues returned
    mock_backend.evaluate.assert_called_once()
    assert len(issues) == 1

def test_ast_policy_security_rejection():
    """Тестирование AST policy rejection dangerous constructs."""
    from polisyos.scientist.governance.legal.ast_policy import ASTPolicy, SecurityError

    policy = ASTPolicy()

    # Test dangerous constructs are rejected
    dangerous_exprs = [
        "__import__('os').system('hack')",
        "eval('1+1')",
        "open('/etc/passwd').read()",
        "globals()['__builtins__']",
        "x.__class__.__bases__[0].__subclasses__()",
    ]

    for expr in dangerous_exprs:
        with pytest.raises(SecurityError):
            policy.validate_expression(expr)

def test_safe_expression_evaluation():
    """Тестирование safe expression evaluator."""
    from polisyos.scientist.governance.legal.backends.expr_ast import SafeExpressionEvaluator

    evaluator = SafeExpressionEvaluator()

    # Test safe mathematical expressions
    result = evaluator.evaluate("x + y * 2", {"x": 1, "y": 3})
    assert result == 7

    # Test error handling
    with pytest.raises(ValueError):  # Division by zero
        evaluator.evaluate("1 / 0", {})

    with pytest.raises(NameError):  # Missing variable
        evaluator.evaluate("undefined_var + 1", {})
```

## Troubleshooting

### Распространенные проблемы

**Legal pass profile issues:**
```bash
# LegalPass runs only in STRICT profile by default
pytest tests/scientist/governance/test_legal_pass.py::test_legal_pass_skips_in_fast_profile -v
# Use enabled=True to force execution in other profiles
pytest tests/scientist/governance/test_legal_pass.py::test_legal_pass_force_enabled_runs_in_fast -v
```

**Norm pack validation failures:**
```bash
# Проверьте schema compliance
pytest tests/scientist/governance/test_legal_pass.py::test_norm_pack_json_roundtrip -v
# Проверьте rule structure
pytest tests/scientist/governance/test_legal_pass.py::test_norm_pack_rule_types -v
```

**Backend protocol issues:**
```bash
# Проверьте backend implementation
pytest tests/scientist/governance/test_legal_pass.py::test_stub_backend_returns_info_issues -v
# Проверьте protocol conformance
pytest tests/scientist/governance/test_legal_pass.py::test_stub_backend_is_runtime_checkable -v
```

**Phase 18 expression evaluation failures:**
```bash
# Проверьте что dangerous constructs правильно отвергаются
pytest tests/scientist/governance/test_norm_execution.py::TestSecurityRejection -v
# Проверьте AST policy validation
pytest tests/scientist/governance/test_norm_execution.py::TestASTPolicy -v
# Проверьте safe expression evaluators
pytest tests/scientist/governance/test_norm_execution.py::TestSafeExpressionEvaluator -v
```

**Pipeline orchestration issues:**
```bash
# Проверьте short-circuit logic
pytest tests/scientist/governance/test_validation_pipeline.py -k "blocker" -v
# Проверьте pass ordering
pytest tests/scientist/governance/test_validation_pipeline.py -k "ordering" -v
```

## Технологии и зависимости

### Core Dependencies
- **Core Contracts**: Legal contracts и validation schemas
- **IR Structures**: Norm pack structures и policy representations
- **Pydantic v2**: Schema validation и type safety

### Validation Infrastructure
- **Validation Pipeline**: Orchestrator для passes с short-circuit logic
- **Compliance Issues**: Structured feedback с severity levels
- **Pass Context**: Shared state management между passes
- **Validation Profiles**: Fast/mvp/strict конфигурации

### Legal Components
- **Legal Pass**: Profile-based legal validation с pluggable backends
- **Rule Backend System**: Protocol-based architecture для rule evaluators
- **Stub Backend**: Reference implementation для testing
- **Norm Pack Contracts**: Structured legal norms (NormPack, NormRule, NormRef)

### Phase 18 Security Components
- **AST Policy System**: Static analysis для expression security
- **Safe Expression Evaluation**: AST-based security validation
- **Expression Evaluators**: Safe computation environment
- **Security Validation**: Attack vector prevention и construct rejection
- **AST Limits**: Node count, depth limits, complexity constraints