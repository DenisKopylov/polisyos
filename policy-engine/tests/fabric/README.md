# Fabric Tests

Комплексная валидация компонентов Fabric layer - ingestion pipeline, evidence bundles, trust system и materialization engine.

**Последнее обновление:** Январь 2026
**Уровень:** Fabric Layer (Data Ingestion & Trust)
**Зависимости:** Core artifacts, DuckDB, Kuzu, pandas

## Архитектурный контекст

Fabric layer отвечает за ingestion и обработку внешних данных, обеспечение их качества и доверия. Тесты валидируют полный pipeline от raw data до curated artifacts с provenance tracking и uncertainty quantification.

## Структура тестов

```
fabric/
├── test_data_catalog.py           # Data Contract catalog system, contract validation, metric bindings, search
├── test_evidence_bundle.py        # Evidence bundles, ingestion pipeline, provenance tracking
└── test_trust_two_pass.py         # Trust system, uncertainty bounds, двухпроходное сравнение
```

## Категории тестов

### Data Contract Catalog (`test_data_catalog.py`)

**Цель:** Комплексная валидация системы каталогов данных - контрактов, привязок метрик, поиска и registry системы.

**Ключевые тесты:**
- **Data Contract Validation**: Валидация структур контрактов данных (DataContract, DataContractCollection) с типами, гранулярностью, PII уровнями
- **Metric Binding Integrity**: Hash-интегрированные привязки метрик к контрактам с проверкой целостности и immutable свойствами
- **Metric Searcher Disambiguation**: Fuzzy search и разрешение метрик с логикой disambiguation, confidence scoring и deprecated handling
- **Contract Registry System**: Загрузка, валидация и управление каталогом контрактов с error handling для missing/invalid контрактов
- **DuckDB Type Mapping**: Bootstrap tool для маппинга типов DuckDB в DataType enum (int/float/string/array/json и т.д.)

**Принципы:**
- **Contract Immutability**: Контракты данных неизменяемы (frozen models) после создания
- **Hash Integrity**: Детерминированные хэши для обнаружения изменений в контрактах
- **Search Disambiguation**: Автоматическое разрешение неоднозначных запросов с confidence thresholds
- **Type Safety**: Строгая типизация и валидация всех компонентов каталога
- **PII Classification**: Многоуровневая классификация персональных данных (None/Low/Medium/High)
- **Deprecation Support**: Пометка устаревших метрик с указанием successors

### Evidence Bundle (`test_evidence_bundle.py`)

**Цель:** Валидация ingestion pipeline и evidence tracking для всех данных в системе.

**Ключевые тесты:**
- **Evidence Mandatory**: FabricResult контракты требуют evidence_ref (Law E enforcement)
- **Ingestion Pipeline**: Raw → Staging → Curated трансформация с data quality checks
- **Evidence Persistence**: Создание и хранение evidence артефактов после ingestion
- **Provenance Tracking**: Полная traceability происхождения данных

**Принципы:**
- **Evidence as Proof**: Каждый результат ingestion сопровождается evidence bundle
- **Three-stage Pipeline**: Raw (сырые данные) → Staging (предварительная обработка) → Curated (очищенные данные)
- **Data Quality Gates**: Валидация качества данных на каждом этапе
- **Immutable Evidence**: Evidence bundles неизменяемы и versioned

### Trust System (`test_trust_two_pass.py`)

**Цель:** Валидация системы доверия к данным с uncertainty quantification.

**Ключевые тесты:**
- **Two-pass Comparison**: Двухпроходное сравнение для optimistic/pessimistic сценариев
- **Uncertainty Bounds**: Расчет и persistence доверительных интервалов
- **Statistical Guarantees**: Математическая корректность оценок неопределенности
- **Trust Policies**: Многоуровневые политики доверия к источникам данных

**Принципы:**
- **Risk Assessment**: Одновременное рассмотрение лучших/худших сценариев
- **Uncertainty Quantification**: Статистическая оценка неопределенности с bounds
- **Cryptographic Verification**: Криптографические гарантии целостности данных
- **Trust Levels**: Иерархическая система уровней доверия к источникам

## Запуск тестов

```bash
# Все fabric тесты
pytest tests/fabric/ -v

# Конкретные компоненты
pytest tests/fabric/test_data_catalog.py -v
pytest tests/fabric/test_evidence_bundle.py -v
pytest tests/fabric/test_trust_two_pass.py -v
```

## Связи с другими модулями

### Зависимости Fabric Layer

**Core Layer** (`core/`):
- **Artifact Store**: Хранение evidence bundles, trust metrics и catalog контрактов
- **Canonical JSON**: Нормализованная сериализация для детерминированных хэшей контрактов

**Runtime Layer** (`runtime/`):
- **Ingestion Jobs**: Управление жизненным циклом ingestion процессов

### Потребители Fabric Layer

**Scientist Layer** (`scientist/`):
- **Policy Specification**: Использование catalog метрик для определения policy variables и constraints
- **Data Discovery**: Поиск доступных метрик через MetricSearcher для policy authoring

**Foundry Layer** (`foundry/`):
- **Calibration Targets**: Catalog метрики как цели калибровки параметров с типами и units
- **Trust Integration**: Использование uncertainty bounds в calibration
- **Evidence-based Validation**: Валидация данных через evidence bundles

**Integration Layer** (`integration/`):
- **Data Pipeline**: Полный цикл от ingestion до simulation с catalog metadata
- **UDF Engine**: User defined functions для сложных data transformations с type validation

### Архитектурные инварианты

- **Contract First**: Все метрики должны иметь контракты в catalog перед использованием
- **Hash Integrity**: Изменения контрактов обнаруживаются через hash mismatch validation
- **Search Mandatory**: Scientist не может использовать произвольные имена метрик без поиска
- **Закон E**: Evidence обязательны (FabricResult всегда содержит evidence_ref)
- **Закон H**: Evidence обязательны (data провода фиксируют provenance/evidence)
- **Закон I**: Trust policies (многоуровневые политики доверия к источникам данных)
- **Materialization Engine**: Инкрементальная материализация реляционных представлений

## Разработка и расширение

### Добавление новых fabric тестов

1. **Data Catalog Tests**: Тестируйте контракты с различными типами данных, гранулярностью и PII уровнями
2. **Binding Tests**: Проверяйте hash integrity и immutability binding'ов
3. **Search Tests**: Тестируйте fuzzy matching, disambiguation и confidence scoring
4. **Registry Tests**: Валидируйте загрузку, error handling и contract validation
5. **Integration Tests**: Используйте реальные базы данных (DuckDB/Kuzu) для integration-style тестов
6. **Evidence Tests**: Проверяйте evidence bundles для всех результатов ingestion
7. **Trust Tests**: Валидируйте trust metrics и uncertainty bounds
8. **Failure Tests**: Тестируйте failure scenarios и error handling
9. **Provenance Tests**: Проверяйте provenance tracking через всю pipeline

### Структура fabric теста

```python
def test_ingestion_creates_evidence(tmp_path: Path) -> None:
    # Setup: create raw data
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    # Execute: run ingestion
    result = run_ingestion(raw_dir=raw_dir, ...)

    # Verify: check evidence bundle
    assert result.evidence_ref is not None
    evidence = store.get_json(result.evidence_ref.artifact_id)
    assert evidence["ingestion_method"] == "standard_pipeline"
```

## Troubleshooting

### Распространенные проблемы

**Data contract validation failures:**
```bash
# Проверьте структуру контрактов
pytest tests/fabric/test_data_catalog.py::TestDataContract::test_valid_contract_creation -v
# Валидируйте metric_id pattern и required fields
pytest tests/fabric/test_data_catalog.py::TestDataContract::test_invalid_metric_id_rejected -v
```

**Metric binding hash mismatches:**
```bash
# Проверьте hash integrity binding'ов
pytest tests/fabric/test_data_catalog.py::TestMetricBinding::test_binding_hash_changes_with_contract -v
# Убедитесь что contracts immutable
pytest tests/fabric/test_data_catalog.py::TestDataContract::test_contract_immutability -v
```

**Search disambiguation issues:**
```bash
# Проверьте fuzzy matching
pytest tests/fabric/test_data_catalog.py::TestMetricSearcher::test_fuzzy_match_unemployment -v
# Валидируйте confidence thresholds
pytest tests/fabric/test_data_catalog.py::TestMetricSearcher::test_ambiguous_query_needs_disambiguation -v
```

**Registry loading errors:**
```bash
# Проверьте загрузку contracts из файла
pytest tests/fabric/test_data_catalog.py::TestDataContractRegistry::test_registry_loads_contracts -v
# Валидируйте error handling для missing contracts
pytest tests/fabric/test_data_catalog.py::TestDataContractRegistry::test_registry_get_missing_raises -v
```

**Evidence bundle creation failures:**
```bash
# Проверьте что ingestion pipeline завершается успешно
pytest tests/fabric/test_evidence_bundle.py::test_run_ingestion_writes_evidence -v
# Убедитесь что raw/staging/curated директории существуют
```

**Trust system calculation errors:**
```bash
# Проверьте двухпроходное сравнение
pytest tests/fabric/test_trust_two_pass.py::test_two_pass_compare_bounds -v
# Валидируйте математическую корректность bounds
```

**Database connection issues:**
```bash
# Проверьте что Kuzu доступен
pytest.importorskip("kuzu")
# Очистите тестовые базы данных
rm -f tmp_path/*.duckdb tmp_path/*.kuzu
```

**Ingestion pipeline failures:**
```bash
# Проверьте структуру CSV файлов
head tmp_path/raw/*.csv
# Валидируйте schema compliance
pytest tests/fabric/test_evidence_bundle.py -v --tb=long
```

## Технологии и зависимости

### Core Dependencies
- **DuckDB**: Columnar storage для staging/curated данных
- **Kuzu**: Graph database для relational представлений
- **pandas**: Data manipulation и ETL operations

### Fabric-Specific Components
- **Data Contract Catalog**: Структурированные контракты данных с типами, гранулярностью и PII уровнями
- **Metric Binding System**: Hash-интегрированные привязки метрик к контрактам
- **Metric Searcher**: Fuzzy search и disambiguation для разрешения метрик
- **Contract Registry**: Управление каталогом контрактов с валидацией
- **Ingestion Pipeline**: Raw → Staging → Curated трансформация
- **Evidence Bundles**: Артефакты результатов ingestion с provenance
- **Trust Engine**: Статистическая верификация доверия к данным
- **Materializer Engine**: Инкрементальная материализация представлений

### Integration Points
- **Core Artifacts**: Immutable хранение всех fabric результатов и catalog контрактов
- **Scientist Layer**: Data discovery и policy specification через catalog search
- **Runtime Manifests**: Управление ingestion jobs и их lifecycle
- **UDF Engine**: Complex data transformations с type validation из catalog
- **Calibration Engine**: Использование catalog метаданных для parameter optimization