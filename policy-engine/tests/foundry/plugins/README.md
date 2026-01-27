# Foundry Plugin System Tests

Тесты модульной плагинной архитектуры Foundry layer с capability-based plugin registry.

**Последнее обновление:** Январь 2026
**Уровень:** Foundry Layer / Plugin System
**Зависимости:** JAX, Plugin API, Core registry

## Архитектурный контекст

Plugin System предоставляет модульную архитектуру для расширения Foundry layer. Тесты валидируют PluginRegistry, CompositeExecutor, domain configurations и capability system, обеспечивая корректную интеграцию плагинов с симуляционным ядром.

## Структура тестов

```
plugins/
└── test_plugin_system.py      # PluginRegistry, CompositeExecutor, EconomicsPlugin, domain configs
```

## Категории тестов

### Plugin Registry (`PluginRegistry`)

**Цель:** Валидация регистрации, поиска и управления плагинами.

**Ключевые тесты:**
- **Plugin Registration**: Регистрация плагинов с валидацией метаданных
- **Plugin Discovery**: Поиск плагинов по имени и capability
- **Duplicate Prevention**: Предотвращение дублированной регистрации
- **Registry State**: Управление состоянием registry (clear, list, get)

**Принципы:**
- **Capability-based Design**: Плагины регистрируют свои возможности
- **Metadata Validation**: Строгая валидация метаданных плагинов
- **Thread Safety**: Безопасная работа в многопоточной среде

### Composite Executor (`CompositeExecutor`)

**Цель:** Оркестрация execution через multiple domains.

**Ключевые тесты:**
- **State Composition**: Комбинирование состояний из разных domains
- **Execution Ordering**: Правильная последовательность выполнения плагинов
- **Domain Isolation**: Независимое управление domain-specific logic
- **Error Handling**: Graceful handling ошибок в composite execution

**Принципы:**
- **Domain Separation**: Четкое разделение ответственности между domains
- **State Consistency**: Гарантии consistency при композиции состояний
- **Execution Coordination**: Координированное выполнение между плагинами

### Economics Plugin (`EconomicsPlugin`)

**Цель:** Тестирование специализированного экономического плагина.

**Ключевые тесты:**
- **Economic Mechanisms**: Валидация экономических моделей и механизмов
- **Agent Integration**: Корректная интеграция с агентной симуляцией
- **Policy Effects**: Проверка эффектов экономических политик
- **State Management**: Управление экономическим состоянием

**Принципы:**
- **Economic Modeling**: Аккуратное моделирование экономических процессов
- **Agent Behavior**: Влияние экономических факторов на поведение агентов
- **Policy Simulation**: Корректная симуляция экономических политик

### Domain Configuration (`DomainConfig`)

**Цель:** Настройка domain-specific параметров и constraints.

**Ключевые тесты:**
- **Config Validation**: Валидация конфигураций domains
- **Parameter Binding**: Правильная привязка параметров к domains
- **Constraint Enforcement**: Enforcement domain-specific ограничений
- **Config Inheritance**: Наследование и переопределение конфигураций

**Принципы:**
- **Declarative Configuration**: Декларативное определение domain configs
- **Validation Rules**: Строгие правила валидации конфигураций
- **Inheritance Hierarchy**: Поддержка иерархии конфигураций

### Capability System (`PluginCapability`)

**Цель:** Проверка compatibility и feature detection плагинов.

**Ключевые тесты:**
- **Capability Declaration**: Корректное объявление возможностей плагинов
- **Compatibility Checking**: Проверка совместимости между плагинами
- **Feature Detection**: Автоматическое обнаружение функциональности
- **Capability Matching**: Matching требований к возможностям

**Принципы:**
- **Explicit Declaration**: Явное объявление возможностей
- **Type Safety**: Type-safe capability checking
- **Extensibility**: Легкое добавление новых capabilities

### Auto Registration (`auto_register_plugins`)

**Цель:** Автоматическое обнаружение и загрузка плагинов.

**Ключевые тесты:**
- **Plugin Discovery**: Автоматическое обнаружение плагинов в системе
- **Registration Process**: Корректная регистрация обнаруженных плагинов
- **Error Handling**: Обработка ошибок при auto-registration
- **Plugin Loading**: Правильная загрузка и инициализация плагинов

**Принципы:**
- **Convention over Configuration**: Автоматическое обнаружение по конвенциям
- **Safe Loading**: Безопасная загрузка с error recovery
- **Dynamic Updates**: Поддержка динамического обновления плагинов

## Запуск тестов

```bash
# Все тесты plugin system
pytest tests/foundry/plugins/ -v

# Конкретные компоненты
pytest tests/foundry/plugins/test_plugin_system.py::TestPluginRegistry -v
pytest tests/foundry/plugins/test_plugin_system.py::TestCompositeExecutor -v
pytest tests/foundry/plugins/test_plugin_system.py::TestEconomicsPlugin -v
pytest tests/foundry/plugins/test_plugin_system.py::TestDomainConfig -v
pytest tests/foundry/plugins/test_plugin_system.py::TestPluginCapability -v
pytest tests/foundry/plugins/test_plugin_system.py::TestAutoRegistration -v
```

## Конфигурация окружения

### JAX Configuration (conftest.py в корне)
```python
# CPU enforcement для consistency
os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```

### Plugin Dependencies
- **Plugin API**: Core plugin interfaces и contracts
- **Domain Registry**: Registry для domain configurations
- **Capability Framework**: Framework для capability management

## Связи с другими модулями

### Зависимости Plugin System

**Core Layer** (`core/`):
- **Registry System**: Использование core registry для plugin metadata

**Foundry Layer** (`foundry/`):
- **Simulation Core**: Интеграция плагинов с симуляционным ядром
- **State Management**: Управление composite state через плагины

### Потребители Plugin System

**Scientist Layer** (`scientist/`):
- **Policy Compilation**: Использование плагинов для различных типов политик

**Integration Layer** (`integration/`):
- **Workflow Extensions**: Расширение workflows через плагины

### Архитектурные инварианты

- **Capability Enforcement**: Все плагины должны объявлять свои capabilities
- **Domain Isolation**: Domains остаются изолированными в composite execution
- **Plugin Lifecycle**: Корректное управление жизненным циклом плагинов

## Разработка и расширение

### Добавление новых plugin тестов

1. **Для registry**: Тестируйте регистрацию новых типов плагинов
2. **Для composite execution**: Проверяйте взаимодействие между domains
3. **Для capabilities**: Валидируйте новые capability types
4. **Для domain configs**: Тестируйте различные конфигурационные сценарии

### Структура plugin теста

```python
def test_plugin_component():
    # Setup: create plugin components
    plugin = TestPlugin()
    registry = PluginRegistry()

    # Execute: register and use plugin
    registry.register(plugin)
    result = registry.execute_with_capability(PluginCapability.TEST)

    # Verify: check plugin behavior
    assert result.success
    assert len(result.plugins_used) > 0
```

## Troubleshooting

### Распространенные проблемы

**Plugin registration failures:**
```bash
# Проверьте capability declarations
pytest tests/foundry/plugins/test_plugin_system.py::TestPluginRegistry::test_register_plugin -v
```

**Composite execution issues:**
```bash
# Проверьте domain isolation
pytest tests/foundry/plugins/test_plugin_system.py::TestCompositeExecutor -v
```

**Capability matching problems:**
```bash
# Проверьте capability types
pytest tests/foundry/plugins/test_plugin_system.py::TestPluginCapability -v
```

**Auto-registration failures:**
```bash
# Проверьте plugin discovery paths
pytest tests/foundry/plugins/test_plugin_system.py::TestAutoRegistration -v
```

## Технологии и зависимости

### Core Plugin Framework
- **Plugin API**: Интерфейсы для плагинов и registry
- **Capability System**: Type-safe capability declarations
- **Domain Framework**: Domain-specific configuration и execution

### Integration Components
- **JAX Integration**: Plugin integration с JAX computations
- **State Management**: Composite state handling для multi-domain execution

### Discovery System
- **Import System**: Python import hooks для plugin discovery
- **Metadata Parsing**: Parsing plugin metadata для registration