# IR Tests

Валидация загрузчиков, преобразователей IR структур и универсального policy interface.

**Последнее обновление:** Январь 2026
**Уровень:** IR Layer (Policy Representation)
**Зависимости:** Pydantic v2, Core contracts

## Архитектурный контекст

IR layer обеспечивает универсальный интерфейс для работы с политиками в различных форматах. Тесты валидируют загрузчики, type safety и schema compatibility.

## Структура тестов

```
ir/
└── test_loaders.py            # Загрузчики политик из различных форматов
```

## Категории тестов

### Policy Loaders (`test_loaders.py`)

**Цель:** Валидация универсального интерфейса для загрузки политик из различных форматов.

**Ключевые тесты:**
- **Pass-through Loading**: Прозрачная обработка уже загруженных PolicySurfaceIR объектов
- **Mapping Loading**: Загрузка из словарей/mapping с type safety
- **Format Compatibility**: Поддержка различных representation formats
- **Validation Integration**: Type checking и schema validation при загрузке

**Принципы:**
- **Universal Interface**: Единый API для всех форматов представления политик
- **Type Safety**: Принудительная типизация и валидация на этапе загрузки
- **Pass-through Optimization**: Избегание unnecessary преобразований
- **Schema Versioning**: Поддержка versioning схем с backward compatibility

## Запуск тестов

```bash
# Все IR тесты
pytest tests/ir/ -v

# Конкретные компоненты
pytest tests/ir/test_loaders.py -v
```

## Связи с другими модулями

### Зависимости IR Layer

**Core Layer** (`core/`):
- **Contracts**: IR структуры определены через core contracts
- **Validation**: Schema validation через core validation framework

### Потребители IR Layer

**Scientist Layer** (`scientist/`):
- **Policy Compilation**: IR → executable foundry programs
- **Surface IR**: Semantic model для policy manipulation

**Foundry Layer** (`foundry/`):
- **IR Compilation**: Преобразование IR в executable simulation code

### Архитектурные инварианты

- **Закон C**: Contracts как источник истины (структура определена в IR, экспортируется в JSON Schema)
- **Schema Evolution**: Безопасные миграции между версиями IR
- **Type Safety**: Строгая валидация типов и структур
- **Universal Loading**: Единый интерфейс для всех policy formats

## Разработка и расширение

### Добавление новых IR тестов

1. Тестируйте все supported formats загрузки
2. Проверяйте type safety и validation errors
3. Валидируйте schema compatibility
4. Тестируйте pass-through optimizations

### Структура IR теста

```python
def test_load_policy_from_format():
    # Setup: create policy в target format
    policy_data = create_policy_in_format(format_type)

    # Execute: load через universal interface
    loaded = load_policy(policy_data)

    # Verify: check correctness и type
    assert isinstance(loaded, PolicySurfaceIR)
    validate_policy_structure(loaded)
```

## Troubleshooting

### Распространенные проблемы

**Schema validation failures:**
```bash
# Проверьте schema compatibility
pytest tests/ir/test_loaders.py -v --tb=long
```

**Type conversion errors:**
```bash
# Проверьте type safety в loaders
pytest tests/ir/test_loaders.py::test_load_policy_from_mapping_surface -v
```

## Технологии и зависимости

### Core Dependencies
- **Pydantic v2**: Data validation и type safety
- **Core Contracts**: IR schema definitions

### Loading Infrastructure
- **Universal Loaders**: Format-agnostic policy loading
- **Type Validation**: Runtime type checking и conversion
- **Schema Management**: Version-aware schema handling