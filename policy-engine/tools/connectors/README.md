# Connectors - Инструменты для работы с коннекторами данных

Набор инструментов для разработки, тестирования и валидации коннекторов данных Policy Engine. Обеспечивает быструю разработку compliant коннекторов с автоматической генерацией boilerplate кода.

## Структура папки

```
connectors/
└── scaffold.py                 # Генератор скелетов коннекторов
```

## Быстрый старт

Все инструменты запускаются из корня проекта:

```bash
cd policy-engine/

# Создание нового REST коннектора
python tools/connectors/scaffold.py create --name WorldBankData --type REST

# Создание SQL коннектора
python tools/connectors/scaffold.py create --name PostgresEcon --type SQL

# Создание CSV коннектора с dry-run
python tools/connectors/scaffold.py create --name CensusData --type CSV --dry-run
```

## scaffold.py - Генератор скелетов коннекторов

Инструмент для автоматической генерации compliant коннекторов данных с полным набором boilerplate кода. Генерирует готовые к использованию коннекторы, которые проходят ConnectorTestHarness из коробки.

### Поддерживаемые типы коннекторов

**REST** - Для REST API источников данных:
- Capabilities: FULL_FETCH, DATE_RANGE_FILTER, RATE_LIMIT_AWARE
- Методы: connect(), disconnect(), fetch(), health_check()
- Опционально: get_dataset_schema(), list_datasets()

**CSV** - Для CSV файлов и потоков:
- Capabilities: FULL_FETCH, SCHEMA_INTROSPECTION
- Методы: connect(), disconnect(), fetch(), health_check(), get_dataset_schema()
- Автоматическое определение схемы из заголовков

**SQL** - Для реляционных баз данных:
- Capabilities: FULL_FETCH, DATE_RANGE_FILTER, SCHEMA_INTROSPECTION
- Методы: connect(), disconnect(), fetch(), health_check(), get_dataset_schema()
- Поддержка SQL INFORMATION_SCHEMA для introspection

**SDMX** - Для статистических данных SDMX:
- Capabilities: FULL_FETCH, CATALOG_BROWSE, STREAMING, FRESHNESS_CHECK
- Методы: connect(), disconnect(), fetch(), health_check()
- Дополнительно: list_datasets(), fetch_stream(), check_freshness()

### Что генерируется

**Исходный код коннектора** (`src/polisyos/fabric/connectors/sources/{snake_name}.py`):
- Полный класс наследник BaseConnector
- Корректные импорты и type hints
- Metadata с connector_id, capabilities, trust_level
- Заглушки всех обязательных методов
- Специфичные для типа дополнительные методы

**Тестовый код** (`tests/fabric/connectors/sources/test_{snake_name}.py`):
- Полный тест класс наследующий ConnectorTestHarness
- Sample конфигурация и схема для тестирования
- Все необходимые fixtures и mocks
- Готовые к запуску тесты

### Примеры использования

```bash
# Создание REST коннектора для экономических данных
python tools/connectors/scaffold.py create --name FRED --type REST

# Результат:
# - src/polisyos/fabric/connectors/sources/fred.py
# - tests/fabric/connectors/sources/test_fred.py

# Создание с кастомным namespace
python tools/connectors/scaffold.py create --name IMFData --type SDMX --namespace imf

# Создание с предварительным просмотром
python tools/connectors/scaffold.py create --name ECBData --type REST --dry-run

# Перезапись существующего коннектора
python tools/connectors/scaffold.py create --name ExistingConnector --type SQL --force
```

### Архитектурная интеграция

Генерируемые коннекторы следуют архитектурным законам Policy Engine:

**Закон A (Направленный граф зависимостей):**
- Коннекторы могут импортировать только fabric.* и ir.* модули
- Запрещены импорты scientist.* (LLM нарушает data layer)
- Изоляция от orchestration уровня

**Закон C (Контракты как источник истины):**
- Автоматическая генерация metadata с правильными capability declarations
- Валидные connector_id и namespace форматы
- Соответствие TrustLevel и QualityTier контрактам

**Закон E (Evidence и provenance):**
- FetchResult включает provenance_ref
- DataVersion для evidence tracking
- Интеграция с CAS системой

### Следующие шаги после генерации

1. **Заполните TODO секции** в сгенерированном коннекторе
2. **Запустите линтер** для проверки архитектурной корректности:
   ```bash
   python tools/lint_connectors.py --connector custom.fred
   ```
3. **Запустите тесты** для валидации интерфейсов:
   ```bash
   python -m pytest tests/fabric/connectors/sources/test_fred.py -v
   ```
4. **Зарегистрируйте коннектор** в ConnectorRegistry (см. docs/connectors/CONTRIBUTING.md)

### Интеграция с модулями

- **`polisyos.fabric.connectors.base.BaseConnector`** - базовый интерфейс
- **`polisyos.fabric.connectors.types`** - типы данных и контракты
- **`polisyos.ir.connectors`** - IR контракты для коннекторов
- **`polisyos.fabric.connectors.testing.ConnectorTestHarness`** - тестовая инфраструктура

## CI/CD интеграция

Рекомендуется включать генерацию в процесс разработки:

```yaml
# Проверка сгенерированных коннекторов
- name: Lint connectors
  run: python tools/lint_connectors.py

# Тестирование коннекторов
- name: Test connectors
  run: python -m pytest tests/fabric/connectors/ -v
```

## Troubleshooting

### Ошибка "already exists"
```bash
# Используйте --force для перезаписи
python tools/connectors/scaffold.py create --name MyConnector --type REST --force
```

### Ошибка namespace
```bash
# Namespace должен содержать только буквы, цифры и подчеркивания
python tools/connectors/scaffold.py create --name MyConnector --type REST --namespace my_namespace
```

### Не поддерживаемый тип
```bash
# Проверьте поддерживаемые типы
python tools/connectors/scaffold.py create --help
# Поддерживаемые типы: REST, CSV, SQL, SDMX
```

### Import ошибки в тестах
```bash
# Убедитесь что PYTHONPATH корректный
export PYTHONPATH="/path/to/policy-engine/src:$PYTHONPATH"
python -m pytest tests/fabric/connectors/sources/test_my_connector.py
```

## Разработка новых шаблонов

### Добавление нового типа коннектора

1. Добавьте тип в `VALID_TYPES` в scaffold.py
2. Реализуйте `_source_template()` для нового типа
3. Определите capabilities и дополнительные методы
4. Обновите документацию

### Кастомизация шаблонов

Шаблоны в `scaffold.py` легко расширяемы. Для добавления новых возможностей:

- Модифицируйте `capability_map` для новых capabilities
- Добавьте новые `optional_stubs` для специфичных методов
- Обновите `metadata` generation логику

---

*Инструмент scaffold протестирован с Python 3.11+ и генерирует коннекторы совместимые с текущей архитектурой Policy Engine. Документация актуальна на 2026-02-05.*