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
├── test_evidence_bundle.py        # Evidence bundles, ingestion pipeline, provenance tracking
└── test_trust_two_pass.py         # Trust system, uncertainty bounds, двухпроходное сравнение
```

## Категории тестов

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
pytest tests/fabric/test_evidence_bundle.py -v
pytest tests/fabric/test_trust_two_pass.py -v
```

## Связи с другими модулями

### Зависимости Fabric Layer

**Core Layer** (`core/`):
- **Artifact Store**: Хранение evidence bundles и trust metrics
- **Canonical JSON**: Нормализованная сериализация для детерминированных хэшей

**Runtime Layer** (`runtime/`):
- **Ingestion Jobs**: Управление жизненным циклом ingestion процессов

### Потребители Fabric Layer

**Foundry Layer** (`foundry/`):
- **Trust Integration**: Использование uncertainty bounds в calibration
- **Evidence-based Validation**: Валидация данных через evidence bundles

**Integration Layer** (`integration/`):
- **Data Pipeline**: Полный цикл от ingestion до simulation
- **UDF Engine**: User defined functions для сложных data transformations

### Архитектурные инварианты

- **Закон E**: Evidence обязательны (FabricResult всегда содержит evidence_ref)
- **Закон H**: Evidence обязательны (data провода фиксируют provenance/evidence)
- **Закон I**: Trust policies (многоуровневые политики доверия к источникам данных)
- **Materialization Engine**: Инкрементальная материализация реляционных представлений

## Разработка и расширение

### Добавление новых fabric тестов

1. Используйте реальные базы данных (DuckDB/Kuzu) для integration-style тестов
2. Проверяйте evidence bundles для всех результатов ingestion
3. Валидируйте trust metrics и uncertainty bounds
4. Тестируйте failure scenarios и error handling
5. Проверяйте provenance tracking через всю pipeline

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
- **Ingestion Pipeline**: Raw → Staging → Curated трансформация
- **Evidence Bundles**: Артефакты результатов ingestion с provenance
- **Trust Engine**: Статистическая верификация доверия к данным
- **Materializer Engine**: Инкрементальная материализация представлений

### Integration Points
- **Core Artifacts**: Immutable хранение всех fabric результатов
- **Runtime Manifests**: Управление ingestion jobs и их lifecycle
- **UDF Engine**: Complex data transformations с security passes