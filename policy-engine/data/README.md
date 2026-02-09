# Policy Engine Data Layer

## Обзор

Папка `data/` представляет собой **Unified Data Fabric** (UDF) - унифицированную систему управления данными Policy Engine. Это сердце системы симуляции политик, обеспечивающее безопасный, структурированный и воспроизводимый доступ к данным. Архитектура поддерживает полный жизненный цикл данных от сырых исходников до готовых аналитических датасетов.

## Архитектура данных

### Слои данных (Data Layers)

```
Raw → Staging → Curated
```

#### `raw/`: Исходные данные
- **Назначение**: Неизменяемые исходные данные из внешних источников
- **Формат**: CSV файлы, JSON, другие форматы
- **Текущее состояние**: Пустая директория (`.gitkeep`)
- **Назначение**: Хранилище для загрузки внешних данных перед обработкой

#### `staging/`: Промежуточная обработка
- **Назначение**: Нормализованные данные после первичной валидации и очистки
- **Формат**: Apache Parquet (эффективное columnar-хранилище)
- **Текущие датасеты**:
  - `agents.parquet` - характеристики агентов (экономические субъекты)
  - `macro.parquet` - макроэкономические показатели по шагам симуляции
  - `interactions.parquet` - взаимодействия между агентами
- **Процессы**: Валидация схем, очистка данных, нормализация типов, базовая трансформация

#### `curated/`: Финальные аналитические данные
- **Назначение**: Готовые к использованию данные с полной метаданными и качественными метриками
- **Формат**: Parquet + JSON манифесты + контракты данных
- **Текущие компоненты**:
  - Dataset манифесты (`*_manifest.json`) - метаданные качества и происхождения
  - Data contracts (`data_contracts.json`) - семантические контракты метрик
  - UDF схема (`udf_schema.json`) - конфигурация безопасного доступа к данным
  - Entity resolution манифест (`entity_resolution_manifest.json`)
- **Особенности**: Entity resolution, reconciliation, quality metrics, provenance tracking

#### `norms/`: Правовые нормы и правила
- **Назначение**: Хранилище нормативных правил для compliance-проверок политик
- **Формат**: YAML файлы с декларативными правилами
- **Текущие файлы**:
  - `sample_norms.yaml` - примеры норм из различных юрисдикций (EU Maastricht Treaty, US Budget Control Act, Ukrainian Budget Code, etc.)
- **Связь с системой**: Интегрируется с `scientist.governance.legal` модулем для валидации политик
- **Поддерживаемые бэкенды**: `expr_ast` (выражения), `llm` (LLM-интерпретация), `stub` (заглушка)

## Основные сущности данных

### Agents (Агенты)
Экономические субъекты в симуляции с поведенческими характеристиками.

**Поля**:
- `run_id`: Идентификатор прогона симуляции
- `step`: Шаг симуляции
- `agent_id`: Уникальный идентификатор агента
- `age`: Возраст агента
- `income`: Текущий доход
- `savings`: Накопления
- `is_employed`: Статус занятости (boolean)

**PII уровень**: Высокий (agent_id - sensitive)

### Macro History (Макроэкономические показатели)
Временные ряды макроэкономических индикаторов по шагам симуляции.

**Поля**:
- `run_id`: Идентификатор прогона симуляции
- `step`: Шаг симуляции
- `gdp`: ВВП (номинальный)
- `unemployment_rate`: Уровень безработицы (доля)
- `inflation_rate`: Уровень инфляции (процент)
- `avg_price`: Средняя цена товаров
- `avg_income`: Средний доход по популяции
- `government_balance`: Баланс государственного бюджета

**PII уровень**: Низкий (публичные макроданные)

### Interactions (Взаимодействия)
Экономические транзакции и взаимодействия между агентами.

**Поля**:
- `run_id`: Идентификатор прогона симуляции
- `from_id`: Идентификатор отправителя
- `to_id`: Идентификатор получателя
- `step`: Шаг симуляции
- `amount`: Сумма транзакции
- `type`: Тип взаимодействия (paid_tax, transfer, subsidy, etc.)

**PII уровень**: Средний (идентификаторы агентов)

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
      "inflation_rate", "avg_price", "avg_income", "government_balance",
      "timestamp"
    ],
    "agents_snapshot": [
      "run_id", "step", "agent_id", "age", "income", "savings", "is_employed"
    ]
  },
  "allowed_relation_types": ["paid_tax", "transfer"],
  "field_classification": {
    "macro_history": {
      "run_id": "internal",
      "step": "public",
      "gdp": "public",
      "unemployment_rate": "public",
      "inflation_rate": "public",
      "avg_price": "public",
      "avg_income": "public",
      "government_balance": "public",
      "timestamp": "internal"
    },
    "agents_snapshot": {
      "run_id": "internal",
      "step": "internal",
      "agent_id": "sensitive",
      "age": "internal",
      "income": "internal",
      "savings": "internal",
      "is_employed": "internal"
    }
  }
}
```

**Уровни доступа**:
- `public`: Открытые данные (доступны всем)
- `internal`: Внутренние данные (для анализа и разработки)
- `sensitive`: Чувствительные данные (требуют специального разрешения, PII)

### Data Contracts
Семантические контракты метрик для стандартизации и валидации:

```json
{
  "contracts": [
    {
      "metric_id": "us.macro.gdp_nominal",
      "display_name": "Nominal GDP",
      "dtype": "float",
      "unit": "billion_usd",
      "pii_tier": "none",
      "source_table": "macro_history",
      "source_column": "gdp"
    }
  ]
}
```

## Правовые нормы (Norms)

### Обзор
Папка `norms/` содержит декларативные правила для compliance-проверок политик. Нормы интегрируются с системой governance для автоматической валидации предлагаемых политик на соответствие юридическим требованиям.

### Структура норм
```yaml
norms:
  - norm_id: "MAASTRICHT_DEFICIT"
    provision_refs:
      - provision_id: "TEU_Art126"
        source_document: "Treaty on European Union"
        version: "2012"
    rule_type: "prohibition"
    description: "Budget deficit must not exceed 3% of GDP"
    backend_refs: ["expr_ast"]
    metadata:
      when: "has_budget_data"
      must_not: "budget_deficit_pct > 3.0"
      message: "Deficit {budget_deficit_pct:.2f}% exceeds Maastricht limit (3%)"
```

### Поддерживаемые типы норм
- **Obligation**: Политика должна удовлетворять условию (`must`)
- **Prohibition**: Политика не должна нарушать условие (`must_not`)
- **Permission**: Политика может выполнять действие (редко используется)

### Бэкенды исполнения
- **`expr_ast`**: Безопасные математические выражения (рекомендуемый)
- **`llm`**: Интерпретация через LLM для сложных норм
- **`stub`**: Заглушка для тестирования

### Примеры норм
- Maastricht Treaty критерии (EU budget rules)
- US Budget Control Act (deficit limits)
- Ukrainian Budget Code (fiscal constraints)
- Labor standards (minimum wage)
- Tax policy (progressive taxation)

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

### Текущее состояние
В данный момент папка содержит демо-данные для тестирования системы:

- **Staging**: Нормализованные Parquet файлы (agents, macro, interactions)
- **Curated**: Манифесты, data contracts, UDF schema
- **Norms**: Примеры правовых норм для различных юрисдикций

### Добавление новых данных

1. **Поместите CSV в `raw/`**
```bash
cp my_new_data.csv data/raw/
```

2. **Запустите ingestion pipeline**
```bash
python -m polisyos.fabric.ingestion --input data/raw/my_new_data.csv
```

3. **Проверьте результат в staging/curated/**
```bash
ls -la data/staging/ data/curated/
```

### Работа с нормами

1. **Добавьте нормы в `norms/`**
```bash
# Создайте новый YAML файл или добавьте в существующий
vim data/norms/custom_norms.yaml
```

2. **Протестируйте валидацию**
```bash
python -c "
from polisyos.ir.norm_pack import NormPack
pack = NormPack.from_yaml('data/norms/sample_norms.yaml')
print(f'Loaded {len(pack.norms)} norms')
"
```

### Проверка качества данных

```bash
# Проверка dataset манифестов
python -c "
import json
with open('data/curated/agents_manifest.json') as f:
    manifest = json.load(f)
    print(f'Quality metrics: {manifest[\"quality\"]}')
    print(f'PII flags: {manifest[\"pii_flags\"]}')
"

# Валидация data contracts
python -c "
from polisyos.fabric.catalog.contract import DataContractRegistry
registry = DataContractRegistry.from_json('data/curated/data_contracts.json')
print(f'Loaded {len(registry.contracts)} contracts')
"
```

### Доступ через UDF (User Defined Functions)

```python
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.ir.analytics.data_views import DataViewRequest, DataViewType

# Создание безопасного запроса к данным
request = DataViewRequest(
    view_type=DataViewType.PANEL,
    dataset="macro_history",
    columns=["gdp", "unemployment_rate"],
    filters=[{"field": "run_id", "op": "eq", "value": "demo_run"}],
    access_tier="public"  # Уровень доступа к PII
)

# Выполнение запроса с проверками безопасности
engine = UDFEngine()
result = engine.execute_view(request)
print(f"Retrieved {len(result.data)} rows")
```

### Работа с нормами в governance

```python
from polisyos.ir.norm_pack import NormPack
from polisyos.scientist.governance.passes.legal_pass import LegalPass

# Загрузка норм
norms = NormPack.from_yaml('data/norms/sample_norms.yaml')

# Создание LegalPass для валидации политик
legal_pass = LegalPass(backend="expr_ast", enabled=True)

# Валидация политики против норм
issues = legal_pass.validate_policy(policy_ir, norms)
for issue in issues:
    print(f"Legal issue: {issue.message}")
```

## Связанные компоненты

### Fabric Layer (Data Processing)
- `fabric/ingestion.py` - ETL пайплайн (CSV → Parquet → Curated)
- `fabric/manifest.py` - генерация dataset манифестов с метаданными
- `fabric/schema.py` - Pydantic схемы валидации данных
- `fabric/io/db.py` - DuckDB адаптер для аналитических запросов
- `fabric/io/graph_store.py` - Kùzu адаптер для графовых данных
- `fabric/evidence.py` - криптографически верифицируемые evidence bundles
- `fabric/fitness_report.py` - оценка качества данных
- `fabric/catalog/` - система контрактов метрик

### UDF Layer (Secure Queries)
- `udf/config.py` - конфигурация уровней доступа (PII tiers)
- `udf/compiler.py` - компилятор DataView запросов с security checks
- `udf/engine.py` - безопасное исполнение UDF запросов
- `udf/schema.py` - схемы запросов и валидация
- `udf/passes/` - компиляторные проходы (privacy, typecheck, etc.)

### Governance & Legal Layer
- `scientist/governance/legal/` - система compliance-проверок
- `scientist/governance/passes/legal_pass.py` - LegalPass для валидации политик
- `scientist/governance/legal/backends/expr_ast.py` - AST бэкенд для выражений
- `scientist/governance/legal/ast_policy.py` - политика безопасности AST
- `ir/norm_pack.py` - структуры данных для норм (NormPack, NormRule)

### IR Layer (Intermediate Representation)
- `ir/data_views.py` - декларативные запросы к данным (DataViewRequest)
- `ir/norm_pack.py` - структуры для правовых норм
- `core/contracts/legal.py` - контракты между модулями

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
через API `run_connectors_ingestion()` из `polisyos.fabric.ingestion`
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

1. **Создайте Pydantic схему** в `src/polisyos/fabric/schema.py`
```python
from pydantic import BaseModel
from datetime import datetime

class NewDatasetRow(BaseModel):
    id: str
    value: float
    timestamp: datetime
    category: str | None = None

    class Config:
        extra = "forbid"
```

2. **Добавьте в UDF schema** `data/curated/udf_schema.json`
```json
{
  "allowed_columns": {
    "new_dataset": ["id", "value", "timestamp", "category"]
  },
  "field_classification": {
    "new_dataset": {
      "id": "internal",
      "value": "public",
      "timestamp": "public",
      "category": "public"
    }
  }
}
```

3. **Создайте data contract** в `data/curated/data_contracts.json`
```json
{
  "metric_id": "custom.new_value",
  "display_name": "New Value Metric",
  "dtype": "float",
  "source_table": "new_dataset",
  "source_column": "value",
  "pii_tier": "none"
}
```

4. **Обновите ingestion pipeline** в `src/polisyos/fabric/ingestion.py`

### Добавление новых норм

1. **Создайте YAML файл норм** в `data/norms/`
```yaml
norms:
  - norm_id: "CUSTOM_RULE"
    provision_refs:
      - provision_id: "CUSTOM_LAW_1"
        source_document: "Custom Regulation"
    rule_type: "obligation"
    backend_refs: ["expr_ast"]
    metadata:
      when: "has_custom_data"
      must: "custom_value <= max_allowed"
      message: "Custom value {custom_value} exceeds limit {max_allowed}"
```

2. **Реализуйте бэкенд** если нужен новый тип выражений
```python
# В src/polisyos/scientist/governance/legal/backends/
class CustomBackend(RuleBackend):
    def evaluate_rule(self, rule: NormRule, context: Dict) -> bool:
        # Ваша логика оценки правила
        pass
```

### Кастомная валидация данных

```python
from polisyos.fabric.quality import DataQualityValidator

class CustomValidator(DataQualityValidator):
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        # Кастомная логика валидации
        issues = []
        if (df['value'] <= 0).any():
            issues.append("All values must be positive")

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            metrics={'negative_values': (df['value'] <= 0).sum()}
        )
```

## Ссылки

### Архитектура и дизайн
- [Complete Architecture Overview](../../architecture.md)
- [Policy Engine README](../../README.md)
- [Fabric Layer Documentation](../src/polisyos/fabric/README.md)
- [UDF System Documentation](../src/polisyos/fabric/udf/README.md)

### Governance & Legal
- [Legal Compliance System](../src/polisyos/scientist/governance/README.md)
- [NormPack IR Documentation](../src/polisyos/ir/README.md)
- [Legal Backends](../src/polisyos/scientist/governance/legal/README.md)

### Инструменты и демо
- [Fabric Layer Documentation](../src/polisyos/fabric/README.md)
- [Data Diagnostics](../tools/diagnostics/check_setup.py)
- [Schema Generation](../tools/diagnostics/gen_schema.py)

### Спецификации
- [Policy IR Schema](../../schemas/snapshots/ir/trinity_bundle.schema.json)
- [Data Contracts Schema](../src/polisyos/fabric/catalog/README.md)
- [UDF Security Model](../src/polisyos/fabric/udf/README.md)
