# Integration Tests

Проверка end-to-end сценариев через все слои системы с использованием реальных баз данных и внешних зависимостей.

**Последнее обновление:** 5 февраля 2026
**Уровень:** Integration Layer (End-to-End Scenarios)
**Зависимости:** DuckDB, Kuzu, UDF Engine, LLM APIs, Full system stack

## Архитектурный контекст

Integration тесты проверяют полный цикл работы системы от draft до decision, используя реальные базы данных и внешние зависимости. Они маркированы `@pytest.mark.integration` для раздельного запуска от unit тестов.

## Структура тестов

```
integration/
├── test_calibration_udf.py    # Калибровка параметров с UDF движком и историческими данными
├── test_workflow_smoke.py     # Полный smoke-test pipeline (draft → simulate → governor → decision)
└── test_workflow_llm.py       # Интеграция с LLM компонентами и языковыми моделями
```

## Категории тестов

### Calibration UDF (`test_calibration_udf.py`)

**Цель:** Калибровка параметров с использованием UDF движка для получения целевых значений из исторических данных.

**Ключевые тесты:**
- **UDF Target Fetching**: Получение calibration targets через User Defined Functions
- **Historical Data Integration**: Использование исторических данных из simulation databases
- **Parameter Recovery**: Валидация что calibration восстанавливает правильные параметры
- **UDF Engine Integration**: Полная интеграция с UDF движком и security passes

**Принципы:**
- **Real Databases**: Использование реальных DuckDB/Kuzu баз с тестовыми данными
- **UDF-based Targets**: Сложные objective functions через user-defined functions
- **Historical Baselines**: Калибровка по историческим данным и baseline runs
- **Security Passes**: UDF execution с security validation

### Workflow Smoke Test (`test_workflow_smoke.py`)

**Цель:** Полный smoke-test pipeline от draft до decision с валидацией всех промежуточных артефактов.

**Ключевые тесты:**
- **End-to-End Pipeline**: Полный цикл draft → IR → compilation → simulation → governor → decision
- **Artifact Validation**: Проверка всех промежуточных артефактов и их integrity
- **State Transitions**: Корректные переходы между этапами workflow
- **Result Consistency**: Согласованность результатов через всю pipeline

**Принципы:**
- **Full Pipeline Coverage**: Тестирование всех этапов от начала до конца
- **Artifact Chain Validation**: Проверка provenance и integrity каждого артефакта
- **State Machine Correctness**: Правильные переходы в workflow state machine
- **Result Verification**: End-to-end валидация correctness

### LLM Workflow (`test_workflow_llm.py`)

**Цель:** Тестирование интеграции с языковыми моделями, prompt engineering и workflow orchestration.

**Ключевые тесты:**
- **LLM-based IR Generation**: Создание IR структур через LLM компоненты
- **Prompt Engineering**: Валидация prompt templates и их эффективности
- **Workflow Orchestration**: Комплексные сценарии с AI-компонентами
- **State Machine Transitions**: Правильные переходы в AI-powered workflows

**Принципы:**
- **AI Integration**: Полная интеграция с LLM компонентами и prompt engineering
- **Complex Scenarios**: Тестирование state machine transitions с AI
- **Template Validation**: Проверка prompt templates и их robustness
- **Orchestration Logic**: Валидация workflow coordination с AI components

## Запуск тестов

```bash
# Все integration тесты (медленные, с БД)
pytest tests/integration/ -v

# Конкретные компоненты
pytest tests/integration/test_calibration_udf.py -v
pytest tests/integration/test_workflow_smoke.py -v
pytest tests/integration/test_workflow_llm.py -v

# С меткой integration (для раздельного запуска)
pytest -m integration -v
```

## Связи с другими модулями

### Зависимости Integration Layer

**Все слои системы** используются в integration тестах:
- **Scientist**: LLM-driven policy drafting, workflow orchestration
- **IR**: Policy compilation и validation
- **Fabric**: Data ingestion, evidence bundles, trust system
- **Foundry**: Simulation execution, calibration system
- **Runtime**: Run lifecycle management, artifact persistence
- **Core**: Artifact storage, registry system

### Архитектурные инварианты

- **Full Pipeline Testing**: Draft → IR → Compilation → Simulation → Governor → Decision
- **Real Databases**: Использование DuckDB/Kuzu вместо mocks
- **Integration Markers**: `@pytest.mark.integration` для CI/CD separation
- **End-to-End Validation**: Проверка корректности через все слои

## Разработка и расширение

### Добавление новых integration тестов

1. Используйте `@pytest.mark.integration` маркер
2. Создавайте реальные базы данных с тестовыми данными
3. Тестируйте полный end-to-end workflow
4. Проверяйте все intermediate artifacts
5. Валидируйте cross-layer contracts

### Структура integration теста

```python
@pytest.mark.integration
def test_full_pipeline_workflow(tmp_path: Path):
    # Setup: create databases, baseline data
    db_path = tmp_path / "test.duckdb"
    setup_baseline_data(db_path)

    # Execute: run full pipeline
    result = run_end_to_end_workflow(db_path, ...)

    # Verify: check all artifacts and final decision
    assert result.decision_packet is not None
    validate_artifact_chain(result)
```

## Troubleshooting

### Распространенные проблемы

**Database connection issues:**
```bash
# Очистите тестовые базы данных
rm -f tmp_path/integration.duckdb tmp_path/integration.kuzu
pytest tests/integration/ -v
```

**UDF engine failures:**
```bash
# Проверьте что UDF dependencies установлены
python -c "from polisyos.fabric.udf.engine import UDFEngine; print('UDF OK')"
pytest tests/integration/test_calibration_udf.py -v
```

**LLM API timeouts:**
```bash
# Integration тесты с LLM могут требовать API ключей
pytest tests/integration/test_workflow_llm.py --tb=short
# Проверьте LLM_API_KEY environment variable
```

**Memory issues в full pipeline:**
```bash
# Запускайте по одному тесту
pytest tests/integration/test_workflow_smoke.py -v -s
```

**Artifact validation failures:**
```bash
# Проверьте artifact integrity
pytest tests/integration/test_workflow_smoke.py::test_workflow_smoke_approve -v --tb=long
```

## Технологии и зависимости

### Database Systems
- **DuckDB**: Columnar analytics database для simulation results
- **Kuzu**: Graph database для relational data и complex queries

### AI/ML Components
- **LLM Integration**: Language models для policy drafting
- **Prompt Engineering**: Template-based AI interaction
- **State Machines**: Complex workflow orchestration

### Data Processing
- **UDF Engine**: User Defined Functions с security passes
- **Calibration Engine**: Parameter optimization с historical data
- **Data Views**: Structured access to simulation results

### Full System Integration
- **Artifact Chain**: Immutable artifacts через всю pipeline
- **Evidence Bundles**: Provenance tracking для всех data
- **Trust System**: Uncertainty quantification в results