# Legal Compliance Validation: Правовая валидация политик

**Модульная система проверки соответствия экономических политик юридическим нормам с pluggable backends**

Legal validation layer обеспечивает проверку соответствия сгенерированных политик юридическим нормам через модульную систему backends. Поддерживает различные типы норм (обязательства, запреты, разрешения) и позволяет интегрировать различные движки оценки правил.

## Обзор

Папка `legal/` реализует систему проверки compliance экономических политик с юридическими нормами. Архитектура построена на принципах pluggability - новые backends для оценки норм могут добавляться без изменения существующего кода.

## Архитектура

```
legal/
├── __init__.py           # Экспорт основных компонентов
├── ast_policy.py         # Новые структуры политик для legal validation (в разработке)
├── backends/
│   ├── __init__.py       # Экспорт backends
│   ├── base.py           # RuleBackend протокол и базовые типы
│   ├── expr_ast.py       # AST-based backend для expression evaluation
│   └── stub.py           # Stub backend для тестирования
└── README.md             # Эта документация
```

## Компоненты

### 🔧 RuleBackend Protocol (backends/base.py)

Базовый протокол для всех реализаций legal backends:

```python
from typing import Protocol, runtime_checkable
from polisyos.ir.norm_pack import NormPack

@runtime_checkable
class RuleBackend(Protocol):
    """Protocol for rule evaluation backends."""

    @property
    def backend_id(self) -> str:
        """Unique identifier for the backend implementation."""
        ...

    def evaluate(
        self,
        norm_pack: "NormPack",
        context: dict,
    ) -> List[ComplianceIssue]:
        """Evaluate policy compliance against legal norms.

        Args:
            norm_pack: Collection of legal norms to evaluate against
            context: Evaluation context (policy IR, metadata, etc.)

        Returns:
            List of compliance issues found during evaluation
        """
        ...
```

**Ключевые требования к backends:**
- **Idempotent**: Повторные вызовы с одинаковыми входами дают одинаковые результаты
- **Stateless**: Не хранят состояние между вызовами
- **Thread-safe**: Могут использоваться в параллельных контекстах
- **Error handling**: Graceful degradation при ошибках

### 📋 Типы норм и структур данных

Система работает с тремя основными типами юридических норм:

#### RuleType Enum
```python
class RuleType(str, Enum):
    OBLIGATION = "obligation"    # Обязательства (должно выполняться)
    PROHIBITION = "prohibition"  # Запреты (нельзя нарушать)
    PERMISSION = "permission"    # Разрешения (можно при определенных условиях)
```

#### NormRule Structure
```python
@dataclass
class NormRule:
    norm_id: str                    # Уникальный идентификатор нормы
    provision_refs: List[NormRef]   # Ссылки на законодательные акты
    rule_type: RuleType            # Тип нормы
    description: str               # Человеко-читаемое описание
    backend_refs: List[str]        # Поддерживаемые backends
    conditions: Optional[dict]     # Условия применения нормы
    metadata: Optional[dict]       # Дополнительные метаданные
```

#### NormPack Collection
```python
@dataclass
class NormPack:
    pack_id: str                   # Идентификатор пакета норм
    jurisdiction: str             # Юрисдикция (EU, US, RU, etc.)
    effective_date: str           # Дата вступления в силу
    norms: List[NormRule]         # Список норм в пакете
    metadata: Optional[dict]      # Метаданные пакета
```

### 🧪 StubBackend (backends/stub.py)

Базовая реализация для тестирования и development:

```python
class StubBackend:
    """Stub implementation that returns 'not implemented' for all norms."""

    @property
    def backend_id(self) -> str:
        return "stub"

    def evaluate(
        self,
        norm_pack: "NormPack",
        context: dict,
    ) -> List[ComplianceIssue]:
        """Return INFO issues for all norms indicating they're not implemented."""

        issues = []
        for norm in norm_pack.norms:
            issues.append(ComplianceIssue(
                pass_name="legal_pass",
                code=f"NORM_NOT_IMPLEMENTED_{norm.norm_id}",
                message=f"Legal norm '{norm.norm_id}' evaluation not implemented in {self.backend_id} backend",
                severity=IssueSeverity.INFO,
                details={
                    "norm_id": norm.norm_id,
                    "rule_type": norm.rule_type.value,
                    "backend_id": self.backend_id
                }
            ))
        return issues
```

**Использование StubBackend:**
- **Testing**: Тестирование LegalPass интеграции без реальной оценки норм
- **Development**: Разработка governance pipeline до реализации production backends
- **CI/CD**: Базовая проверка что legal validation не ломает workflow

### 🌳 AST Backend (backends/expr_ast.py)

Продвинутая реализация на базе AST (Abstract Syntax Tree) для безопасной оценки expression-based норм:

```python
class ExprASTBackend:
    """AST-based backend for evaluating expression-based legal norms."""

    @property
    def backend_id(self) -> str:
        return "expr_ast"

    def evaluate(
        self,
        norm_pack: "NormPack",
        context: dict,
    ) -> List[ComplianceIssue]:
        """Evaluate norms using AST-based expression evaluation."""

        issues = []
        policy_ir = context.get("policy_ir")

        for norm in norm_pack.norms:
            if not self._supports_norm(norm):
                continue

            # AST-based evaluation
            try:
                result = self._evaluate_norm_ast(norm, policy_ir, context)
                if not result.compliant:
                    issues.append(self._create_compliance_issue(norm, result))

            except Exception as e:
                issues.append(self._create_evaluation_error(norm, e))

        return issues
```

**Ключевые возможности AST Backend:**
- **Safe evaluation**: AST parsing предотвращает code injection
- **Expression support**: Поддержка математических и логических выражений
- **Policy introspection**: Доступ к параметрам и структурам TrinityBundle
- **Error recovery**: Graceful handling evaluation errors

### 🚀 LLM Backend (Планируемый)

Будущая реализация на базе LLM для оценки комплексных текстовых норм:

```python
class LLMBackend:
    """LLM-based backend for evaluating complex textual legal norms."""

    @property
    def backend_id(self) -> str:
        return "llm"

    def evaluate(self, norm_pack: "NormPack", context: dict) -> List[ComplianceIssue]:
        # Integration with Claude/GPT for legal norm evaluation
        # Support for natural language legal requirements
        # Confidence scoring and explanation generation
        pass
```

## Интеграция с LegalPass

Legal validation интегрируется в governance pipeline через LegalPass:

```python
from polisyos.scientist.governance.passes.legal_pass import LegalPass
from polisyos.scientist.governance.legal.backends.stub import StubBackend

# Создание LegalPass с backend
legal_pass = LegalPass(backend=StubBackend())

# Использование в governance pipeline
state = {
    "run_id": "test_legal",
    "norm_pack": load_norm_pack("gdpr_norms"),
    "policy_ir": trinity_bundle
}

issues = legal_pass.validate(PassContext(
    ir=trinity_bundle,
    state=state,
    profile=get_profile("strict"),  # Legal pass только в strict
    run_id="test_legal"
))
```

## API Использование

### Создание кастомного backend

```python
from polisyos.scientist.governance.legal.backends.base import RuleBackend
from polisyos.ir.norm_pack import NormPack, ComplianceIssue, IssueSeverity

class CustomBackend(RuleBackend):
    """Custom rule evaluation backend."""

    @property
    def backend_id(self) -> str:
        return "custom"

    def evaluate(self, norm_pack: NormPack, context: dict) -> List[ComplianceIssue]:
        """Implement custom rule evaluation logic."""

        issues = []
        # Custom evaluation logic here
        return issues
```

### Работа с нормами

```python
from polisyos.ir.norm_pack import NormPack, NormRule, NormRef, RuleType

# Создание нормы
norm = NormRule(
    norm_id="GDPR-5-1-a",
    provision_refs=[
        NormRef(
            provision_id="Art.5.1.a",
            source_document="EU/GDPR/2016"
        )
    ],
    rule_type=RuleType.OBLIGATION,
    description="Data must be processed lawfully",
    backend_refs=["ast", "llm"],
    conditions={"data_processing": True}
)

# Создание пакета норм
norm_pack = NormPack(
    pack_id="gdpr_basic",
    jurisdiction="EU",
    effective_date="2024-01-01",
    norms=[norm]
)
```

### Конфигурация backends

```python
# В LegalPass
legal_pass = LegalPass(
    backend=ExprASTBackend(),
    enabled=True,  # Force enable even in non-strict profiles
    supported_rule_types=[RuleType.OBLIGATION, RuleType.PROHIBITION]
)

# В ValidationPipeline
pipeline.register_pass(legal_pass)
```

## Примеры использования

### GDPR Compliance Check

```python
# Создание GDPR норм
gdpr_norms = NormPack(
    pack_id="gdpr_compliance",
    jurisdiction="EU",
    norms=[
        NormRule(
            norm_id="data_minimization",
            rule_type=RuleType.OBLIGATION,
            description="Personal data shall be adequate, relevant and limited",
            backend_refs=["ast"]
        ),
        NormRule(
            norm_id="consent_required",
            rule_type=RuleType.OBLIGATION,
            description="Consent required for personal data processing",
            backend_refs=["llm"]
        )
    ]
)

# Оценка политики
backend = StubBackend()  # Или ExprASTBackend() для реальной оценки
issues = backend.evaluate(gdpr_norms, {
    "policy_ir": policy_ir,
    "context": {"data_processing": True}
})
```

### Конституционные ограничения

```python
# Конституционные нормы
constitutional_norms = NormPack(
    pack_id="us_constitution",
    jurisdiction="US",
    norms=[
        NormRule(
            norm_id="equal_protection",
            rule_type=RuleType.OBLIGATION,
            description="Equal protection under the law",
            backend_refs=["llm"]
        )
    ]
)
```

## Тестирование

### Unit тесты backends

```bash
# Тестирование legal backends
pytest tests/scientist/governance/test_legal_backends.py -v

# Конкретные backends
pytest tests/scientist/governance/test_legal_stub_backend.py -v
pytest tests/scientist/governance/test_legal_ast_backend.py -v
```

### Mock объекты для тестирования

```python
def create_mock_norm_pack() -> NormPack:
    """Create mock norm pack for testing."""
    return NormPack(
        pack_id="test_pack",
        jurisdiction="TEST",
        effective_date="2024-01-01",
        norms=[
            NormRule(
                norm_id="TEST_1",
                rule_type=RuleType.OBLIGATION,
                description="Test obligation",
                backend_refs=["stub"]
            )
        ]
    )

def test_backend_evaluation():
    """Test backend evaluation with mock data."""
    backend = StubBackend()
    norm_pack = create_mock_norm_pack()

    issues = backend.evaluate(norm_pack, {})

    assert len(issues) == 1
    assert issues[0].code.startswith("NORM_NOT_IMPLEMENTED")
```

### Integration тесты

```python
def test_legal_pass_integration():
    """Test LegalPass integration with governance pipeline."""

    from polisyos.scientist.governance.passes.legal_pass import LegalPass
    from polisyos.scientist.governance.pipeline import ValidationPipeline

    # Setup
    legal_pass = LegalPass(backend=StubBackend(), enabled=True)
    pipeline = ValidationPipeline(profile=get_profile("strict"))

    # Test state
    state = {
        "run_id": "integration_test",
        "norm_pack": create_mock_norm_pack(),
        "policy_ir": create_valid_policy_ir()
    }

    # Execute
    result = pipeline.run(state)

    # Verify legal pass executed
    legal_spans = [span for span in result.validation_trace.pass_spans
                   if span.pass_id == "legal"]
    assert len(legal_spans) == 1
    assert legal_spans[0].issues_count > 0
```

## Расширение

### Добавление нового backend

1. **Реализовать RuleBackend протокол:**
```python
class NewBackend(RuleBackend):
    @property
    def backend_id(self) -> str:
        return "new_backend"

    def evaluate(self, norm_pack: NormPack, context: dict) -> List[ComplianceIssue]:
        # Implementation
        pass
```

2. **Добавить в backends/__init__.py:**
```python
from .new_backend import NewBackend

__all__ = ["NewBackend", ...]
```

3. **Создать тесты и документацию**

### Расширение типов норм

```python
class ExtendedRuleType(str, Enum):
    DEROGATION = "derogation"      # Исключения из правил
    RECOMMENDATION = "recommendation"  # Рекомендации
```

### Кастомные структуры норм

```python
@dataclass
class ExtendedNormRule(NormRule):
    """Extended norm rule with additional fields."""

    severity_level: str = "medium"
    enforcement_mechanism: str = "automatic"
    appeal_process: Optional[str] = None
```

## Связанные компоненты

### IR Layer Integration
- **NormPack, NormRule**: Основные структуры данных из `ir/norm_pack.py`
- **TrinityBundle**: Интеграция с policy evaluation context

### Governance Layer Integration
- **LegalPass**: Основной интеграционный компонент в `passes/legal_pass.py`
- **ValidationPipeline**: Orchestrator для legal validation
- **ComplianceIssue**: Стандартизированный формат результатов

### Core Contracts
- **Legal contracts**: Стабильные интерфейсы в `core/contracts/legal.py`

## Troubleshooting

### Backend не найден

```
ImportError: No module named 'backends.new_backend'
```

**Решение**: Проверить импорт в `backends/__init__.py` и правильность пути

### Norm evaluation failed

```
Exception: Failed to evaluate norm TEST_1: invalid expression
```

**Решение**: Проверить корректность условий нормы и доступность данных в context

### Protocol violation

```
TypeError: X does not implement RuleBackend protocol
```

**Решение**: Убедиться, что кастомный backend реализует все required методы протокола

### Performance issues

**Решение**:
- Cache результаты оценки для одинаковых норм
- Implement batch evaluation для множественных норм
- Add timeouts для LLM-based backends

## Будущие улучшения

### 🚀 Планируемые возможности

- **LLM Backend**: Claude-based evaluation для комплексных норм
- **Multi-jurisdiction**: Одновременная проверка норм из разных юрисдикций
- **Norm versioning**: Поддержка версий норм с автоматическим обновлением
- **Evidence collection**: Автоматический сбор evidence для compliance reporting

### 🔬 Продвинутые возможности

- **Norm conflict detection**: Автоматическое обнаружение конфликтов между нормами
- **Compliance scoring**: Количественная оценка уровня compliance
- **Regulatory change monitoring**: Автоматическое отслеживание изменений в законодательстве
- **Cross-border compliance**: Проверка соответствия нормам разных юрисдикций одновременно
