# Policy Engine Data Layer

## Обзор

Папка `data/` представляет собой **Unified Data Fabric** (UDF) - унифицированную систему управления данными Policy Engine. Это сердце системы симуляции политик, обеспечивающее безопасный, структурированный и воспроизводимый доступ к данным.

## Архитектура данных

### Слои данных (Data Layers)

```
Raw → Staging → Curated
```

#### `raw/`: Исходные данные
- **Назначение**: Неизменяемые исходные данные
- **Формат**: CSV файлы
- **Содержимое**:
  - `agents.csv` - характеристики агентов (экономические субъекты)
  - `macro.csv` - макроэкономические показатели
  - `interactions.csv` - взаимодействия между агентами

#### `staging/`: Промежуточная обработка
- **Назначение**: Нормализованные данные после первичной валидации
- **Формат**: Parquet (эффективное columnar-хранилище)
- **Процессы**: Валидация схем, очистка данных, нормализация типов

#### `curated/`: Финальные данные
- **Назначение**: Готовые к использованию данные с полной метаданными
- **Формат**: Parquet + JSON манифесты
- **Особенности**: Entity resolution, reconciliation, quality metrics

## Основные сущности данных

### Agents (Агенты)
```csv
agent_id,agent_type,age,income,savings,is_employed
agent_1,agent,30,900.0,10.0,True
agent_2,agent,40,1100.0,50.0,True
```

**Поля**:
- `agent_id`: Уникальный идентификатор агента
- `agent_type`: Тип агента (agent, firm, government)
- `age`: Возраст
- `income`: Доход
- `savings`: Сбережения
- `is_employed`: Статус занятости

### Macro (Макроэкономические показатели)
```csv
run_id,step,gdp,unemployment_rate,inflation_rate,avg_price,avg_income,government_balance
demo_run,0,1000.0,0.05,1.0,1.2,900.0,0.0
```

**Поля**:
- `run_id`: Идентификатор прогона симуляции
- `step`: Шаг симуляции
- `gdp`: ВВП
- `unemployment_rate`: Уровень безработицы
- `inflation_rate`: Уровень инфляции
- `avg_price`: Средняя цена
- `avg_income`: Средний доход
- `government_balance`: Баланс бюджета

### Interactions (Взаимодействия)
```csv
from_id,to_id,step,amount,type
agent_1,agent_2,0,100.0,paid_tax
```

**Поля**:
- `from_id`: Отправитель
- `to_id`: Получатель
- `step`: Шаг симуляции
- `amount`: Сумма
- `type`: Тип взаимодействия (paid_tax, transfer, etc.)

## Метаданные и манифесты

### Dataset Manifest
Каждый curated датасет сопровождается JSON манифестом с полной информацией:

```json
{
  "dataset_name": "agents",
  "source": "demo_generator",
  "license": "CC0",
  "raw_hash": "e11e2919bc075132b4a77a59448a5d615468fb5acbf41ae944a8fd8732de4726",
  "schema_version": "1.0",
  "row_count": 3,
  "pii_flags": {
    "agent_id": true
  },
  "quality": {
    "missing_rate": 0.0,
    "duplicate_rate": 0.0,
    "outlier_rate": 0.0,
    "coverage": {
      "time_start": null,
      "time_end": null,
      "region_coverage": null
    }
  },
  "created_at": "2026-01-06T18:36:13.736684"
}
```

**Ключевые поля**:
- `raw_hash`: SHA256 хэш исходного файла для целостности
- `pii_flags`: Флаги персональных данных
- `quality`: Метрики качества (пропуски, дубликаты, выбросы)
- `coverage`: Временной и географический охват

### Entity Resolution Manifest
Отдельный манифест для процесса разрешения сущностей:

```json
{
  "dataset_name": "entity_resolution",
  "row_count": 0,
  "reconciliation": null,
  "quality": {
    "missing_rate": 0.0,
    "duplicate_rate": 0.0
  }
}
```

## UDF Schema (Unified Data Fabric Schema)

### Доступные колонки
```json
{
  "allowed_columns": {
    "macro_history": [
      "run_id", "step", "gdp", "unemployment_rate",
      "inflation_rate", "avg_price", "avg_income", "government_balance"
    ],
    "agents_snapshot": [
      "run_id", "step", "agent_id", "age", "income", "savings", "is_employed"
    ]
  }
}
```

### Классификация полей по PII
```json
{
  "field_classification": {
    "macro_history": {
      "run_id": "internal",
      "step": "public",
      "gdp": "public",
      "agent_id": "sensitive"
    }
  }
}
```

**Уровни доступа**:
- `public`: Открытые данные
- `internal`: Внутренние данные (для анализа)
- `sensitive`: Чувствительные данные (требуют специального разрешения)

### Разрешенные типы отношений
```json
{
  "allowed_relation_types": ["paid_tax", "transfer"]
}
```

## Процесс обработки данных

### Этап 1: Raw → Staging
```python
# fabric/ingestion.py
def ingest_raw_to_staging(csv_path: Path, schema: Type[BaseModel]) -> pd.DataFrame:
    # 1. Загрузка CSV
    df = pd.read_csv(csv_path)

    # 2. Валидация по Pydantic схеме
    valid_df, rejects = _validate_rows(df, schema)

    # 3. Запись в Parquet
    valid_df.to_parquet(staging_path, index=False)

    return valid_df
```

**Действия**:
- Валидация типов данных
- Проверка обязательных полей
- Нормализация форматов
- Запись отклоненных записей в rejects файлы

### Этап 2: Staging → Curated
```python
def stage_to_curated(staging_path: Path) -> DatasetManifest:
    # 1. Entity Resolution
    resolved_df = resolve_entities(staging_df)

    # 2. Reconciliation
    reconciliation = reconcile_with_existing(resolved_df)

    # 3. Quality Assessment
    quality = assess_quality(resolved_df)

    # 4. Generate Manifest
    manifest = DatasetManifest(
        dataset_name=dataset_name,
        raw_hash=_file_hash(raw_path),
        quality=quality,
        pii_flags=detect_pii_flags(resolved_df)
    )

    # 5. Write to Curated
    resolved_df.to_parquet(curated_path)
    manifest.to_json(manifest_path)

    return manifest
```

**Действия**:
- Разрешение сущностей (entity resolution)
- Сверка с существующими данными (reconciliation)
- Оценка качества данных
- Генерация манифеста
- Загрузка в DuckDB/Kùzu

## Работа с данными

### Добавление новых данных

1. **Поместите CSV в `raw/`**
```bash
cp my_new_data.csv data/raw/
```

2. **Запустите ingestion**
```bash
python tools/demos/run_ingest_demo.py
```

3. **Проверьте результат**
```bash
ls -la data/curated/
```

### Проверка качества данных

```bash
# Проверка manifests
python -c "
import json
with open('data/curated/agents_manifest.json') as f:
    manifest = json.load(f)
    print(f'Quality: {manifest[\"quality\"]}')
"
```

### Доступ через UDF

```python
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.ir.data_views import DataViewRequest, DataViewType

# Создание запроса к данным
request = DataViewRequest(
    view_type=DataViewType.PANEL,
    dataset="macro_history",
    columns=["gdp", "unemployment_rate"],
    filters=[{"field": "run_id", "op": "eq", "value": "demo_run"}]
)

# Выполнение запроса
engine = UDFEngine()
result = engine.execute_view(request)
```

## Связанные компоненты

### Fabric Layer
- `fabric/ingestion.py` - основной пайплайн обработки
- `fabric/manifest.py` - генерация манифестов
- `fabric/schema.py` - Pydantic схемы валидации
- `fabric/io/db.py` - DuckDB адаптер
- `fabric/io/graph_store.py` - Kùzu адаптер

### UDF Layer
- `udf/config.py` - конфигурация доступа (PII tiers)
- `udf/compiler.py` - компилятор DataView запросов
- `udf/engine.py` - исполнение запросов
- `udf/schema.py` - схемы запросов

### IR Layer
- `ir/data_views.py` - декларативные запросы к данным

## Безопасность и PII

### Принципы
- **Минимальный доступ**: Только необходимые данные
- **Уровни доступа**: public → internal → sensitive
- **Аудит**: Все запросы логируются
- **Валидация**: Запросы проверяются перед исполнением

### PII Detection
```python
def detect_pii_flags(df: pd.DataFrame) -> dict[str, bool]:
    pii_fields = ['agent_id', 'personal_id', 'ssn']
    return {col: col in pii_fields for col in df.columns}
```

## Диагностика и отладка

### Проверка установки данных
```bash
python tools/diagnostics/check_setup.py
```

### Просмотр логов обработки
```bash
# Логи ingestion
tail -f logs/system.log | grep ingestion
```

### Валидация манифестов
```bash
python -c "
from polisyos.fabric.manifest import DatasetManifest
manifest = DatasetManifest.from_json('data/curated/agents_manifest.json')
print(f'Manifest valid: {manifest.is_valid()}')
"
```

## Производительность

### Рекомендации
- **Parquet**: Эффективное хранение для аналитики
- **Chunked processing**: Обработка большими кусками
- **Memory limits**: Ограничения на размер датасетов
- **Caching**: Кэширование часто используемых данных

### Метрики
- Время ingestion: < 30 сек для 1M записей
- Размер на диске: ~50% от CSV
- Время запроса: < 1 сек для типичных DataView

## Troubleshooting

### Распространенные проблемы

**Ошибка "Manifest not found"**
```
Решение: Запустите ingestion для нужного датасета
python tools/demos/run_ingest_demo.py
```

**Ошибка "PII access denied"**
```
Решение: Проверьте access_tier в DataViewRequest
request.access_tier = AccessTier.INTERNAL
```

**Ошибка "Schema validation failed"**
```
Решение: Проверьте формат CSV файла
python -c "import pandas as pd; pd.read_csv('data/raw/problem.csv').dtypes"
```

## Расширение системы

### Добавление нового датасета

1. **Создайте Pydantic схему** в `fabric/schema.py`
```python
class NewDatasetRow(BaseModel):
    id: str
    value: float
    timestamp: datetime
```

2. **Добавьте в UDF schema** `data/curated/udf_schema.json`
```json
{
  "allowed_columns": {
    "new_dataset": ["id", "value", "timestamp"]
  }
}
```

3. **Обновите ingestion pipeline** в `fabric/ingestion.py`

### Кастомная валидация

```python
def custom_validation(df: pd.DataFrame) -> pd.DataFrame:
    # Ваша логика валидации
    return df[df['value'] > 0]  # Пример: только положительные значения
```

## Ссылки

- [Architecture Overview](../../architecture.md)
- [Fabric Documentation](../src/polisyos/fabric/README.md)
- [UDF Documentation](../src/polisyos/fabric/udf/README.md)
- [Ingestion Demo](../tools/demos/run_ingest_demo.py)
