# Fabric Tests

Комплексная валидация компонентов Fabric layer - ingestion pipeline, evidence bundles, trust system и materialization engine.

**Последнее обновление:** 1 февраля 2026 (добавлены расширенные тесты connectors с reference implementations, cache system, federation, harness, integration, quality system, registry, resilience, schema system, transform pipeline, type system)
**Уровень:** Fabric Layer (Data Ingestion & Trust & Provenance & Quality)
**Зависимости:** Core artifacts, DuckDB, Kuzu, pandas

## Архитектурный контекст

Fabric layer отвечает за ingestion и обработку внешних данных, обеспечение их качества и доверия. Тесты валидируют полный pipeline от raw data до curated artifacts с provenance tracking и uncertainty quantification.

## Структура тестов

```
fabric/
├── connectors/                    # Тесты протокола подключения данных (Data Fabric Connectors)
│   ├── __init__.py                # Пакет connectors тестов
│   └── test_protocol_compliance.py # Protocol compliance, capability validation, error hierarchy, connector metadata
├── test_data_catalog.py           # Data Contract catalog system, contract validation, metric bindings, search
├── test_evidence_bundle.py        # Evidence bundles, ingestion pipeline, provenance tracking
├── test_provenance.py             # Provenance subsystem, entities, graphs, PROV-O export, persistence
├── test_trust_two_pass.py         # Trust system, uncertainty bounds, двухпроходное сравнение
└── test_quality_indicators.py     # Quality indicators system, fitness reports, quality gate pass integration
```

## Категории тестов

### Data Fabric Connectors (`connectors/test_protocol_compliance.py`)

**Цель:** Комплексная валидация протокола подключения данных, capability-based архитектуры, error handling и metadata specification для data fabric connectors.

**Ключевые тесты:**
- **Protocol Compliance Validation**: Валидация что connectors реализуют все required attributes (connector_id, capabilities, metadata) и methods (connect, disconnect, health_check, fetch), проверка capability-method consistency, strict vs lenient validation modes
- **Capability System**: @requires_capability decorator для блокировки вызовов методов при отсутствии capabilities, capability error handling с детальными сообщениями, describe_capabilities utility для анализа capability bitmasks
- **Error Hierarchy**: Структурированная иерархия ошибок наследуемых от ConnectorError (CapabilityError, ConfigurationError, FetchError, RateLimitError), error serialization в dict формат для logging
- **Connection Management**: ConnectionConfig immutability, credential redaction для безопасного logging, connection handle creation, async lifecycle management (connect/disconnect/health_check)
- **Fetch Operations**: FetchRequest hashing для deterministic cache keys, pagination support, filter normalization (порядок не влияет на hash), FetchResult validation с completeness checks
- **Data Versioning**: VersionStrategy enum (TIMESTAMP/CONTENT_HASH/REVISION), version comparison logic, автоматическая UTC coercion для timestamps, immutability guarantees
- **Connector Metadata**: ConnectorMetadataSpec validation с pattern checks для connector_id и version, fully qualified ID generation, capability checking methods, trust level и quality tier validation
- **Validation Framework**: ValidationResult для success/failure states, ValidationIssue с severity levels (ERROR/WARNING), issue aggregation и reporting
- **Capability Helpers**: capabilities_from_flags/flags_from_capabilities для bitmask conversion, roundtrip consistency validation, proper handling capability enums

**Принципы:**
- **Protocol Enforcement**: Strict validation required interface для interoperability между различными data sources
- **Capability-Based Security**: Runtime capability checking предотвращает вызов unsupported operations
- **Immutable Configurations**: Thread-safe design через immutable configs и requests
- **Structured Error Handling**: Consistent error types с rich context для debugging и monitoring
- **Deterministic Behavior**: Stable hashing для caching и request deduplication
- **Version Strategy Flexibility**: Support различных versioning подходов для разных типов data sources
- **Metadata Standardization**: Consistent metadata format для discovery и capability negotiation
- **Async-First Architecture**: All operations async для scalability и non-blocking I/O

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

### Quality Indicators System (`test_quality_indicators.py`)

**Цель:** Комплексная валидация системы оценки качества данных - quality indicators, fitness reports, quality gate pass и их интеграции с governance pipeline.

**Ключевые тесты:**
- **Quality Indicators Calculation**: Точная валидация вычисления quality indicators (missingness, staleness, coverage, outlier ratio) из pandas DataFrames
- **Quality Level Scoring**: Валидация алгоритма определения quality levels (EXCELLENT/GOOD/ACCEPTABLE/POOR/UNUSABLE) с weighted scoring
- **Quality Thresholds Profiles**: Тестирование профилей качества (FAST/MVP/STRICT) с различными tolerance уровнями и overrides
- **Fitness Report Generation**: Создание и валидация human-readable fitness reports с ASCII/markdown форматами
- **Quality Gate Pass Integration**: Интеграция quality validation в governance pipeline с блокировкой на низком качестве данных
- **Schema Drift Detection**: Обнаружение изменений в схеме данных между baseline и текущими колонками
- **Outlier Ratio Calculation**: Вычисление доли выбросов через IQR метод для числовых колонок
- **DuckDB Quality Computation**: Валидация вычисления quality indicators напрямую из DuckDB для больших датасетов

**Принципы:**
- **Multi-dimensional Assessment**: Оценка качества по нескольким измерениям (missingness, staleness, coverage, outliers) с weighted scoring
- **Profile-based Thresholds**: Разные профили качества (FAST/MVP/STRICT) для различных сценариев использования и tolerance уровней
- **Fitness Classification**: Пятиуровневая классификация качества с четкими критериями перехода между уровнями
- **Schema Stability**: Мониторинг изменений схемы данных с penalty за schema drift
- **Outlier Detection**: Статистическое обнаружение выбросов через IQR метод с configurable sensitivity
- **Governance Integration**: Автоматическая блокировка симуляции при низком качестве данных в strict режиме
- **Report Generation**: Создание human-readable отчетов для UI, logging и audit trails в ASCII и Markdown форматах
- **Evidence-based Quality**: Интеграция quality indicators с evidence bundles для end-to-end traceability

### Provenance System (`test_provenance.py`)

**Цель:** Комплексная валидация provenance подсистемы - tracking происхождения данных, activity graphs, PROV-O экспорт и persistence.

**Ключевые тесты:**
- **Provenance Entities**: Валидация сущностей provenance (datasets, metrics, snapshots) с типизацией, immutable свойствами и hash-based identity
- **Provenance Graphs**: Тестирование графов provenance с entities, activities, agents и relations (wasGeneratedBy, used, wasAssociatedWith)
- **PROV-O Export**: Экспорт provenance данных в стандартизированные форматы PROV-JSONLD и PROV-NQUADS
- **Provenance Persistence**: Сохранение и загрузка provenance graphs из artifact store с integrity checks
- **Evidence Bundle Integration**: Интеграция provenance tracking с evidence bundles для end-to-end traceability

**Принципы:**
- **Immutable Entities**: Сущности provenance неизменяемы после создания (frozen dataclasses)
- **Hash-based Identity**: Детерминированные идентификаторы на основе entity_id независимо от других атрибутов
- **Activity Graph**: Полные графы provenance с entities, activities, agents и typed relations
- **PROV-O Standards**: Экспорт в стандартные форматы PROV-O для interoperability
- **Evidence Integration**: Автоматическая генерация provenance graphs из evidence bundles

## Запуск тестов

```bash
# Все fabric тесты
pytest tests/fabric/ -v

# Конкретные компоненты
pytest tests/fabric/connectors/test_protocol_compliance.py -v # Data fabric connectors protocol
pytest tests/fabric/test_data_catalog.py -v
pytest tests/fabric/test_evidence_bundle.py -v
pytest tests/fabric/test_provenance.py -v
pytest tests/fabric/test_trust_two_pass.py -v

# Quality indicators system, fitness reports
pytest tests/fabric/test_quality_indicators.py -v
```

## Связи с другими модулями

### Зависимости Fabric Layer

**Core Layer** (`core/`):
- **Artifact Store**: Хранение evidence bundles, trust metrics и catalog контрактов
- **Canonical JSON**: Нормализованная сериализация для детерминированных хэшей контрактов
- **Data Fabric Connectors**: IR layer определяет connector capabilities и metadata schemas

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
- **Data Fabric Connectors Protocol**: Стандартизированный интерфейс для data source integration с capability-based access control
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
8. **Provenance Tests**: Тестируйте provenance entities, activity graphs и PROV-O экспорт
9. **Failure Tests**: Тестируйте failure scenarios и error handling
10. **Integration Tests**: Проверяйте provenance tracking через всю pipeline с evidence bundles

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

**Provenance graph creation failures:**
```bash
# Проверьте создание provenance entities
pytest tests/fabric/test_provenance.py::TestProvenanceEntity::test_entity_creation -v
# Валидируйте immutable свойства entities
pytest tests/fabric/test_provenance.py::TestProvenanceEntity::test_entity_is_frozen -v
```

**PROV-O export errors:**
```bash
# Проверьте экспорт в PROV-JSONLD
pytest tests/fabric/test_provenance.py::TestProvoExport::test_export_to_provo_jsonld -v
# Валидируйте PROV-NQUADS формат
pytest tests/fabric/test_provenance.py::TestProvoExport::test_export_to_provo_nquads -v
```

**Provenance persistence issues:**
```bash
# Проверьте сохранение provenance graphs
pytest tests/fabric/test_provenance.py::TestProvenancePersistence::test_persist_provenance_graph -v
# Валидируйте загрузку из artifact store
pytest tests/fabric/test_provenance.py::TestProvenancePersistence::test_load_provenance_graph -v
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

**Quality indicators calculation failures:**
```bash
# Проверьте вычисление quality indicators
pytest tests/fabric/test_quality_indicators.py::TestQualityIndicatorsCalculation -v
# Валидируйте missingness calculation
pytest tests/fabric/test_quality_indicators.py::TestQualityIndicatorsCalculation::test_missingness_calculation_half_nulls -v
```

**Quality level scoring issues:**
```bash
# Проверьте quality level determination
pytest tests/fabric/test_quality_indicators.py::TestQualityLevelScoring -v
# Валидируйте excellent quality classification
pytest tests/fabric/test_quality_indicators.py::TestQualityLevelScoring::test_excellent_quality -v
```

**Fitness report generation failures:**
```bash
# Проверьте генерацию fitness reports
pytest tests/fabric/test_quality_indicators.py::TestDataFitnessReport -v
# Валидируйте report summary format
pytest tests/fabric/test_quality_indicators.py::TestDataFitnessReport::test_generate_summary_format -v
```

**Quality gate pass integration issues:**
```bash
# Проверьте integration с governance pipeline
pytest tests/fabric/test_quality_indicators.py::TestQualityGatePassIntegration -v
# Валидируйте strict profile blocking
pytest tests/fabric/test_quality_indicators.py::TestQualityGatePassIntegration::test_strict_profile_blocks_on_poor_quality -v
```

**Schema drift detection failures:**
```bash
# Проверьте обнаружение schema drift
pytest tests/fabric/test_quality_indicators.py::TestQualityIndicatorsCalculation::test_schema_drift_detection -v
# Убедитесь что baseline_columns корректно заданы
```

**Outlier ratio calculation issues:**
```bash
# Проверьте вычисление outlier ratio
pytest tests/fabric/test_quality_indicators.py::TestQualityIndicatorsCalculation::test_outlier_ratio_calculation -v
# Валидируйте что есть числовые колонки для анализа
```

## Технологии и зависимости

### Core Dependencies
- **DuckDB**: Columnar storage для staging/curated данных
- **Kuzu**: Graph database для relational представлений
- **pandas**: Data manipulation и ETL operations

### Fabric-Specific Components
- **Data Fabric Connectors Protocol**: Стандартизированный async интерфейс для data source integration с capability-based access control, error hierarchy и metadata specification
- **Connector Capabilities System**: Bitmask-based capability flags (FULL_FETCH, STREAMING, CATALOG_BROWSE, etc.) с runtime validation через @requires_capability decorator
- **Connector Metadata Specification**: Структурированные метаданные connectors (trust levels, quality tiers, version strategies) с validation patterns
- **Data Version Management**: Version strategies (TIMESTAMP/CONTENT_HASH/REVISION) с comparison logic и UTC timestamp handling
- **Fetch Request Hashing**: Deterministic cache keys для request deduplication с filter normalization и pagination support
- **Connection Configuration**: Immutable configs с credential redaction для безопасного handling sensitive data
- **Validation Framework**: Structured validation results с severity levels и issue aggregation для connector compliance checking
- **Data Contract Catalog**: Структурированные контракты данных с типами, гранулярностью и PII уровнями
- **Metric Binding System**: Hash-интегрированные привязки метрик к контрактам
- **Metric Searcher**: Fuzzy search и disambiguation для разрешения метрик
- **Contract Registry**: Управление каталогом контрактов с валидацией
- **Ingestion Pipeline**: Raw → Staging → Curated трансформация
- **Evidence Bundles**: Артефакты результатов ingestion с provenance
- **Provenance System**: Tracking происхождения данных с PROV-O стандартами и activity graphs
- **Trust Engine**: Статистическая верификация доверия к данным
- **Materializer Engine**: Инкрементальная материализация представлений
- **Quality Indicators System**: Многофакторная оценка качества данных (missingness, staleness, coverage, outliers) с pandas/DuckDB computation
- **Fitness Reports**: Генерация human-readable отчетов о пригодности данных с ASCII/markdown форматами
- **Quality Thresholds**: Configurable профили качества (FAST/MVP/STRICT) с различными tolerance уровнями
- **Quality Gate Pass**: Governance pass для валидации качества данных перед симуляцией

### Integration Points
- **Core Artifacts**: Immutable хранение всех fabric результатов и catalog контрактов
- **Scientist Layer**: Data discovery и policy specification через catalog search
- **Runtime Manifests**: Управление ingestion jobs и их lifecycle
- **UDF Engine**: Complex data transformations с type validation из catalog
- **Calibration Engine**: Использование catalog метаданных для parameter optimization