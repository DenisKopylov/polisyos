# Contract Tests

Обеспечение корректности структур данных и API контрактов на всех уровнях IR, включая валидацию схем, миграции и границы между слоями.

**Последнее обновление:** 1 февраля 2026
**Уровень:** Contract Layer (Schema & API Validation)
**Зависимости:** Pydantic v2, Core contracts

## Архитектурный контекст

Contract тесты обеспечивают корректность границ между слоями и валидность всех структур данных. Они проверяют schema compliance, type safety и API contracts согласно архитектурным законам.

## Структура тестов

```
contract/
├── test_ir_contract.py        # PolicySurfaceIR, селекторы, валидация, TranslatableString
├── test_ir_migrations.py      # Миграции схем IR между версиями
├── test_trinity_contracts.py  # Trinity артефакты: ProblemFrame, PolicySpec, ModelSpec
├── test_trinity_migration.py  # Миграция между Surface IR и Trinity форматами
├── test_fabric_gates.py       # Входные фильтры и предусловия Fabric layer
├── test_kernel_models.py      # Валидация моделей ядра IR (slots, units, merge rules, time semantics)
└── test_surface_ir.py         # Surface IR, линкер, semantic fingerprinting, validation reports
```

## Категории тестов

### IR Contract Validation (`test_ir_contract.py`)

**Цель:** Полная валидация PolicySurfaceIR, селекторов, транслируемых строк, обязательных полей.

**Ключевые тесты:**
- **Required Fields Enforcement**: Валидация обязательных полей в IR структурах
- **Translatable String Aliases**: Корректная обработка языковых алиасов (En/Ua/Ru → en/ua/ru)
- **Selector Validation**: Валидация селекторов и их operators
- **Validation Reports**: Генерация подробных отчетов об ошибках с diff before/after

**Принципы:**
- **Roundtrip Testing**: `yaml → model → yaml` сохраняет канонический формат
- **Alias Acceptance**: Принимает `En/Ua/Ru`, сериализует в `en/ua/ru`
- **Type Safety**: Строгая валидация типов, запрет float значений
- **Schema Compliance**: Полная соответствие IR schema specifications

### IR Schema Migrations (`test_ir_migrations.py`)

**Цель:** Тестирование миграций схем между версиями с сохранением совместимости.

**Ключевые тесты:**
- **Version Transitions**: Безопасные переходы между schema версиями
- **Backward Compatibility**: Поддержка legacy форматов
- **Migration Correctness**: Корректность data transformation при миграциях
- **Schema Evolution**: Управление schema changes over time

**Принципы:**
- **Safe Migrations**: Non-destructive schema transformations
- **Version Tracking**: Explicit version management в IR structures
- **Compatibility Guarantees**: Backward compatibility для existing data
- **Migration Validation**: Testing migration correctness

### Fabric Gates (`test_fabric_gates.py`)

**Цель:** Проверка входных фильтров, предусловий и валидационных барьеров Fabric layer.

**Ключевые тесты:**
- **Input Validation**: Проверка входных данных на соответствие contracts
- **Precondition Enforcement**: Валидация предусловий для data processing
- **Gate Logic**: Корректность фильтров и validation barriers
- **Error Handling**: Appropriate error responses для invalid inputs

**Принципы:**
- **Input Sanitization**: Cleaning и validation входных данных
- **Contract Enforcement**: Strict adherence to FabricResult contracts
- **Quality Gates**: Data quality checks перед processing
- **Error Propagation**: Clear error reporting для invalid data

### Kernel Models (`test_kernel_models.py`)

**Цель:** Комплексная валидация моделей ядра (slots, units, merge rules, time semantics, constraint registry).

**Ключевые тесты:**
- **Slot Validation**: Корректность slot definitions и их properties
- **Unit Systems**: Валидация unit specifications и conversions
- **Merge Rules**: Правильность merge rule definitions и application
- **Time Semantics**: Валидация temporal aspects и time handling
- **Constraint Registry**: Полная валидация constraint definitions

**Принципы:**
- **Type Safety**: Strict typing для всех kernel components
- **Schema Compliance**: Adherence to kernel model specifications
- **Consistency Checks**: Internal consistency validation
- **Registry Integrity**: Correct registry structure и relationships

### Trinity Contracts (`test_trinity_contracts.py`)

**Цель:** Валидация Trinity артефактов (ProblemFrame, PolicySpec, ModelSpec) с типизированными ссылками.

**Ключевые тесты:**
- **ProblemFrame Validation**: Schema compliance, objective/KPI constraints, success criteria
- **PolicySpec Validation**: Intervention structure, mechanism bindings, selector validation
- **ModelSpec Validation**: Data snapshot references, assumption tracking, agent configuration
- **Typed References**: ArtifactID-based references с media type validation
- **TrinityBundle**: Cross-reference consistency между компонентами

**Принципы:**
- **Schema Compliance**: Полная валидация Pydantic схем с custom validators
- **Reference Integrity**: Typed references с guaranteed existence checks
- **Cross-validation**: Consistency между Trinity компонентами
- **Immutable Contracts**: Data integrity через schema constraints

### Trinity Migration (`test_trinity_migration.py`)

**Цель:** Миграция между Surface IR и Trinity форматами с сохранением семантического fingerprint.

**Ключевые тесты:**
- **Split Operations**: Surface IR → ProblemFrame + PolicySpec + ModelSpec
- **Merge Operations**: Trinity components → Surface IR reconstruction
- **Roundtrip Fidelity**: Zero data loss через split/merge cycles
- **Semantic Preservation**: Fingerprint stability после миграции
- **Loader Integration**: Universal loading через load_policy/load_trinity

**Принципы:**
- **Zero Data Loss**: Полная preservation всех semantic elements
- **Idempotent Operations**: Multiple migrations не изменяют результат
- **Backward Compatibility**: Support для legacy Surface IR форматов
- **Schema Evolution**: Safe transitions между IR версиями

### Surface IR (`test_surface_ir.py`)

**Цель:** Тестирование Surface IR, линкера, семантических fingerprint'ов и validation reports.

**Ключевые тесты:**
- **Surface IR Structure**: Валидация complete Surface IR structures
- **Linker Functionality**: Правильность policy linking с mechanisms/constraints
- **Semantic Fingerprinting**: Детерминированные хэши независимо от key order
- **Validation Reports**: Генерация comprehensive error reports с diff analysis

**Принципы:**
- **Semantic Integrity**: Preservation of policy semantics
- **Deterministic Hashing**: Stable fingerprints для policy deduplication
- **Linker Correctness**: Proper binding policies to execution components
- **Error Reporting**: Detailed validation reports с before/after diff

## Запуск тестов

```bash
# Все contract тесты (быстрые, без зависимостей)
pytest tests/contract/ -v

# Конкретные компоненты
pytest tests/contract/test_ir_contract.py -v
pytest tests/contract/test_ir_migrations.py -v
pytest tests/contract/test_trinity_contracts.py -v
pytest tests/contract/test_trinity_migration.py -v
pytest tests/contract/test_fabric_gates.py -v
pytest tests/contract/test_kernel_models.py -v
pytest tests/contract/test_surface_ir.py -v
```

## Связи с другими модулями

### Зависимости Contract Layer

**Core Layer** (`core/`):
- **Contract Definitions**: Base contracts для всех структур данных
- **Validation Framework**: Core validation infrastructure

### Потребители Contract Layer

**Все слои системы** полагаются на contract validation:
- **IR Layer**: Schema compliance для policy structures
- **Fabric Layer**: Input validation и data contracts
- **Foundry Layer**: Type safety для execution components
- **Integration**: Cross-layer contract enforcement

### Архитектурные инварианты

- **Закон C**: Contracts как источник истины (структура определена в IR, экспортируется в JSON Schema)
- **Type Safety**: Strict typing и validation на всех границах
- **Schema Evolution**: Safe schema changes с migration support
- **Contract Enforcement**: Mandatory validation на всех API boundaries

## Разработка и расширение

### Добавление новых contract тестов

1. Тестируйте schema compliance для новых структур данных
2. Проверяйте type safety и validation rules
3. Валидируйте contract boundaries между слоями
4. Тестируйте error handling и validation reports

### Структура contract теста

```python
def test_contract_validation():
    # Setup: create valid/invalid contract data
    valid_data = create_valid_contract()
    invalid_data = create_invalid_contract()

    # Execute: validate contracts
    valid_result = validate_contract(valid_data)
    invalid_result = validate_contract(invalid_data)

    # Verify: check validation results
    assert valid_result.is_valid
    assert not invalid_result.is_valid
    validate_error_reporting(invalid_result)
```

## Troubleshooting

### Распространенные проблемы

**Schema validation failures:**
```bash
# Проверьте schema compliance
pytest tests/contract/test_ir_contract.py::test_required_fields_enforced -v
```

**Type conversion errors:**
```bash
# Проверьте type safety rules
pytest tests/contract/test_ir_contract.py::test_translatable_string_aliases_lowercase_dump -v
```

**Trinity contract failures:**
```bash
# Проверьте schema validation для Trinity артефактов
pytest tests/contract/test_trinity_contracts.py -v
# Проверьте reference integrity
pytest tests/contract/test_trinity_contracts.py::TestTypedReferences -v
```

**Trinity migration failures:**
```bash
# Проверьте semantic fingerprint preservation
pytest tests/contract/test_trinity_migration.py::TestRoundTrip::test_roundtrip_semantic_fingerprint -v
# Проверьте zero data loss
pytest tests/contract/test_trinity_migration.py::TestRoundTrip::test_roundtrip_minimal -v
```

**Migration issues:**
```bash
# Проверьте schema migrations
pytest tests/contract/test_ir_migrations.py -v
```

## Технологии и зависимости

### Core Dependencies
- **Pydantic v2**: Data validation и type enforcement
- **Core Contracts**: Base contract definitions

### Validation Infrastructure
- **Schema Validation**: JSON Schema compliance checking
- **Type Checking**: Runtime type validation
- **Contract Testing**: API boundary validation
- **Migration Framework**: Schema evolution support