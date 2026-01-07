# Policy Engine Tests

Тестовая инфраструктура для Policy Engine - AI-driven Policy Simulation System. Тесты обеспечивают качество кода, валидируют архитектурные границы и проверяют корректность работы всех компонентов системы.

## Архитектурный контекст

Согласно [архитектуре проекта](../architecture.md), тесты организованы по слоям компилятора:

- **IR (Contract Tests)**: Валидация контрактов и схем данных
- **Fabric (Integration Tests)**: Тестирование Unified Data Fabric
- **Foundry (Unit Tests)**: Тестирование JAX-ядра симуляции
- **Scientist (Integration Tests)**: Тестирование оркестрации и workflow

## Структура тестовой иерархии

```
tests/
├── conftest.py              # Конфигурация pytest и настройка окружения
├── contract/                # Тесты контрактов IR и схем валидации
│   ├── test_ir_contract.py      # PolicyRequestIR, TargetSelector, валидация
│   ├── test_ir_migrations.py    # Миграции схем IR
│   └── test_fabric_gates.py     # Входные фильтры Fabric
├── foundry/                 # Тесты симуляционных компонентов
│   ├── test_gradients.py        # Градиенты политик (JAX/Equinox)
│   ├── test_fiscal.py           # Фискальные механизмы
│   ├── test_global_state.py     # Глобальное состояние симуляции
│   ├── test_health.py           # Проверки здоровья системы
│   ├── test_jit_stability.py    # JIT-стабильность
│   ├── test_production_kernel.py # Production kernel
│   └── test_*.py                # Другие тесты foundry
├── integration/             # Интеграционные тесты workflow
│   ├── test_workflow_smoke.py   # Полный smoke-test pipeline
│   └── test_workflow_llm.py     # Интеграция с LLM компонентами
└── scientist/               # Тесты компонентов scientist
    └── test_compiler.py         # Компилятор политик из IR
```

## Категории тестов

### Contract Tests (`contract/`)

**Цель**: Обеспечение корректности структур данных и API контрактов.

**Ключевые тесты:**
- **IR Contract Validation**: Валидация `PolicyRequestIR`, селекторов, транслируемых строк
- **Schema Migrations**: Тестирование миграций схем между версиями
- **Fabric Gates**: Проверка входных фильтров и предусловий

**Принципы:**
- Roundtrip тестирование: `yaml → model → yaml` сохраняет канонический формат
- Alias acceptance: Принимает `En/Ua/Ru`, сериализует в `en/ua/ru`
- Limits enforcement: Огромные payload'ы не "валят пайплайн"
- Entity DAG validation: Циклы в графах сущностей ловятся

### Foundry Tests (`foundry/`)

**Цель**: Валидация математических моделей и симуляций на JAX.

**Ключевые тесты:**
- **Gradient Health**: Проверка градиентов политик, NaN/Inf detection
- **JIT Stability**: Стабильность PyTree структур при компиляции
- **Fiscal Mechanisms**: Тестирование налоговых/субсидий механизмов
- **Kernel Production**: Тестирование production симуляционного ядра

**Принципы:**
- Все тесты форсируют CPU (через conftest.py) для консистентности
- Проверка `jit(step)` компилируется и сохраняет структуру
- Gradient sanity: конечные разности vs JAX autodiff в допусках
- Invariants verification: физическая корректность после шагов симуляции

### Integration Tests (`integration/`)

**Цель**: Проверка end-to-end сценариев через все слои системы.

**Ключевые тесты:**
- **Workflow Smoke Test**: Полный pipeline от IR до DecisionPacket
- **LLM Integration**: Тестирование интеграции с языковыми моделями
- **Budget Constraints**: Проверка ограничений на ресурсы

**Принципы:**
- Маркированы `pytest.mark.integration` для раздельного запуска
- Используют реальные БД (DuckDB/Kuzu) с тестовыми данными
- Проверяют полный цикл: draft → simulate → governor → decision

### Scientist Tests (`scientist/`)

**Цель**: Валидация компонентов ИИ и оптимизации.

**Ключевые тесты:**
- **Policy Compiler**: Компиляция IR в исполняемые модели foundry
- **Self-healing**: Тестирование автоматического исправления ошибок

## Конфигурация окружения (conftest.py)

Файл `conftest.py` обеспечивает консистентное окружение для всех тестов:

### JAX Configuration
```python
# Форсируем CPU для всех тестов (консистентность в CI/CD)
os.environ["JAX_PLATFORM_NAME"] = "cpu"

# Запрещаем аллокацию памяти (экономим ресурсы)
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```

### Logging Setup
```python
# Только ошибки в тестах (убираем шум)
logger.remove()
logger.add(lambda msg: print(msg), level="ERROR")
```

## Запуск тестов

### Базовые команды

```bash
# Все тесты (быстрые unit + медленные integration)
pytest

# Только быстрые unit тесты (foundry + contract)
pytest -m "not integration"

# Только интеграционные тесты (медленные, с БД)
pytest -m integration

# С подробным выводом и остановкой на первой ошибке
pytest -v --tb=short

# С покрытием кода (требует pytest-cov)
pytest --cov=polisyos --cov-report=html
```

### Запуск по категориям

```bash
# Контрактные тесты (быстрые, без зависимостей)
pytest tests/contract/ -v

# Foundry тесты (JAX, математические)
pytest tests/foundry/ -v

# Интеграционные тесты (медленные, с БД)
pytest tests/integration/ -v

# Scientist тесты
pytest tests/scientist/ -v
```

### Специфические сценарии

```bash
# Тесты градиентов (требуют Equinox)
pytest tests/foundry/test_gradients.py

# Тесты workflow (требуют LLM API ключей)
pytest tests/integration/test_workflow_llm.py

# Smoke test (минимальный полный цикл)
pytest tests/integration/test_workflow_smoke.py
```

## Технологии и зависимости

### Core Testing Framework
- **pytest**: Основной фреймворк с плагинами
- **pytest-cov**: Покрытие кода (опционально)

### Domain-Specific Libraries
- **JAX/Equinox**: Для тестирования математических компонентов
- **pandas**: Работа с тестовыми данными
- **DuckDB/Kuzu**: Интеграционные тесты с базами данных
- **Pydantic**: Валидация структур данных

## Принципы тестирования

### Архитектурные инварианты
- **Закон A**: Граф зависимостей только внутрь (scientist → ir/fabric/foundry)
- **Закон B**: Компиляторная труба (NL → LLM → IR → Compilation → Runtime)
- **Закон C**: Контракты как источник истины

### Качественные требования
- **Unit Tests**: Покрывают все публичные API foundry компонентов
- **Contract Tests**: Валидируют границы между слоями
- **Integration Tests**: Проверяют end-to-end сценарии
- **Performance Regression**: SLA на скорость выполнения

### CI/CD интеграция
- Unit тесты запускаются на каждый PR
- Integration тесты - по расписанию или на release
- Архитектурные гейты предотвращают регрессии
- Coverage thresholds для предотвращения снижения качества

## Разработка и расширение

### Добавление новых тестов
1. Определите категорию (contract/foundry/integration/scientist)
2. Следуйте naming convention: `test_*.py`
3. Используйте fixtures из `conftest.py`
4. Маркируйте медленные тесты `@pytest.mark.integration`

### Отладка тестов
```bash
# Запуск с отладкой (останавливается в pdb при ошибке)
pytest --pdb tests/foundry/test_gradients.py::test_tax_subsidy_gradient_value

# Запуск конкретного теста
pytest tests/contract/test_ir_contract.py::test_required_fields_enforced -v
```

### Профилирование
```bash
# Измерение времени выполнения
pytest --durations=10

# Память и CPU profiling (требует дополнительных плагинов)
pytest --profile
```

## Troubleshooting

### Распространенные проблемы

**JAX memory allocation errors:**
```bash
# Решение: проверьте что JAX_PLATFORM_NAME=cpu установлен
export JAX_PLATFORM_NAME=cpu
pytest tests/foundry/
```

**Database connection issues в integration тестах:**
```bash
# Проверьте что тестовые БД не заблокированы предыдущими запусками
rm -f tmp_path/integration.duckdb tmp_path/integration.kuzu
```

**LLM API timeouts:**
```bash
# Integration тесты с LLM могут падать по таймауту
pytest tests/integration/test_workflow_llm.py --tb=short
```

### Полезные команды диагностики

```bash
# Проверка что все зависимости установлены
python tools/diagnostics/check_setup.py

# Генерация схем для проверки контрактов
python tools/diagnostics/generate_ir_schema.py

# Линтинг тест кода
ruff check tests/
```
